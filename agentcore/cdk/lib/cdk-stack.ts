import { AgentCoreApplication, type AgentCoreApplicationProps } from '@aws/agentcore-cdk';
import { CfnResource, RemovalPolicy, Stack, type StackProps } from 'aws-cdk-lib';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';

export interface AgentCoreStackProps extends StackProps {
  /** Props for the AgentCore application, produced by transformAgentCoreJson from agentcore/agentcore.json. */
  application: AgentCoreApplicationProps;
}

/**
 * The stack the AgentCore CLI deploys. Everything declared in agentcore/agentcore.json is
 * created by the AgentCoreApplication construct. Add your own resources below it and wire
 * them to your runtimes and harnesses through the application's accessors.
 */
export class AgentCoreStack extends Stack {
  public readonly application: AgentCoreApplication;

  constructor(scope: Construct, id: string, props: AgentCoreStackProps) {
    super(scope, id, props);
    this.application = new AgentCoreApplication(this, 'Application', props.application);

    // LangGraph checkpoint store for the `agent` runtime (DynamoDBSaver from
    // langgraph-checkpoint-aws). Checkpoints above 350 KB are offloaded to the bucket.
    // No TTL is set by the agent today (CHECKPOINT_TTL_DAYS unset); the TTL attribute is
    // enabled so it can be turned on later without a table change.
    const checkpoints = new dynamodb.Table(this, 'AgentCheckpoints', {
      partitionKey: { name: 'PK', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'SK', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      timeToLiveAttribute: 'ttl',
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
      removalPolicy: RemovalPolicy.RETAIN,
    });
    const checkpointBucket = new s3.Bucket(this, 'AgentCheckpointBucket', {
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      removalPolicy: RemovalPolicy.RETAIN,
    });

    const agent = this.application.runtime('agent');
    checkpoints.grantReadWriteData(agent);
    checkpointBucket.grantReadWrite(agent, 'checkpoints/*');
    agent.addEnvironmentVariable('CHECKPOINT_TABLE', checkpoints.tableName);
    agent.addEnvironmentVariable('CHECKPOINT_BUCKET', checkpointBucket.bucketName);

    // Service-side observability (CloudWatch vended logs). The agent's own OTel spans come from
    // ADOT auto-instrumentation; these deliveries add AgentCore's service logs and traces.
    // Traces go to X-Ray, which requires CloudWatch Transaction Search to be enabled in the account.
    const gateway = this.application.gateway('WebSearchGW');
    const runtimeObs = enableObservability(this, 'AgentRuntimeObservability', {
      name: 'runtime',
      resourceArn: agent.runtimeArn,
      logGroupName: `/aws/vendedlogs/bedrock-agentcore/runtimes/${agent.runtimeId}`,
      logTypes: ['APPLICATION_LOGS', 'USAGE_LOGS'],
    });
    enableObservability(this, 'GatewayObservability', {
      name: 'gateway',
      resourceArn: gateway.gatewayArn,
      logGroupName: `/aws/vendedlogs/bedrock-agentcore/gateways/${gateway.gatewayId}`,
      logTypes: ['APPLICATION_LOGS'],
      after: runtimeObs,
    });
  }
}

interface ObservabilityProps {
  /** Short name used in delivery source/destination names (prefixed with the stack name). */
  readonly name: string;
  /** ARN of the AgentCore resource (runtime, gateway, memory, ...). */
  readonly resourceArn: string;
  /** Log group that receives the CloudWatch Logs deliveries. */
  readonly logGroupName: string;
  /** Log types delivered to CloudWatch Logs. TRACES is always delivered to X-Ray. */
  readonly logTypes: string[];
  /** Delivery to chain after; CloudWatch Logs rejects concurrent delivery changes. */
  readonly after?: CfnResource;
}

/**
 * Wires CloudWatch vended-log deliveries for one AgentCore resource: each log type goes to a
 * dedicated log group, and TRACES goes to X-Ray. Deliveries are created one at a time, and the
 * last delivery is returned so a caller can chain further deliveries after it.
 */
function enableObservability(scope: Construct, id: string, props: ObservabilityProps): CfnResource {
  const root = new Construct(scope, id);
  // Delivery source/destination names are capped at 60 characters.
  const prefix = `${Stack.of(scope).stackName}-${props.name}`;
  const logGroup = new logs.LogGroup(root, 'LogGroup', {
    logGroupName: props.logGroupName,
    retention: logs.RetentionDays.ONE_MONTH,
    removalPolicy: RemovalPolicy.DESTROY,
  });
  const cwlDestination = new logs.CfnDeliveryDestination(root, 'LogsDestination', {
    name: `${prefix}-cwl`,
    destinationResourceArn: logGroup.logGroupArn,
  });
  const xrayDestination = new logs.CfnDeliveryDestination(root, 'TracesDestination', {
    name: `${prefix}-xray`,
    deliveryDestinationType: 'XRAY',
  });

  let previous = props.after;
  const deliveries: Array<[string, logs.CfnDeliveryDestination]> = [
    ...props.logTypes.map((t): [string, logs.CfnDeliveryDestination] => [t, cwlDestination]),
    ['TRACES', xrayDestination],
  ];
  for (const [logType, destination] of deliveries) {
    const suffix = logType.toLowerCase().replace(/_/g, '-');
    const source = new logs.CfnDeliverySource(root, `${logType}Source`, {
      name: `${prefix}-${suffix}`,
      logType,
      resourceArn: props.resourceArn,
    });
    const delivery = new logs.CfnDelivery(root, `${logType}Delivery`, {
      deliverySourceName: source.ref,
      deliveryDestinationArn: destination.attrArn,
    });
    delivery.addResourceDependency(source);
    delivery.addResourceDependency(destination);
    if (previous) delivery.addResourceDependency(previous);
    previous = delivery;
  }
  return previous!;
}
