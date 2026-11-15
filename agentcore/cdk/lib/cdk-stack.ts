import { AgentCoreApplication, type AgentCoreApplicationProps } from '@aws/agentcore-cdk';
import { RemovalPolicy, Stack, type StackProps } from 'aws-cdk-lib';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
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
  }
}
