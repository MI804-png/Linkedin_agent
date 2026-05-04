# Deploy Everything Using AWS CloudShell (Browser Console)

## What is AWS CloudShell?
CloudShell is a **free browser-based terminal** built into AWS Console. No software installation needed!

---

## 🚀 EASIEST METHOD - Deploy in 5 Minutes!

### Step 1: Open AWS CloudShell
1. Go to AWS Console: https://console.aws.amazon.com
2. **Make sure you're in EU-West-1 (Ireland) region** (top-right corner)
3. Click the **CloudShell icon** (looks like `>_` terminal) in the top navigation bar
   - Or search for "CloudShell" in the search bar
4. Wait 10-20 seconds for CloudShell to start
5. You'll see a terminal prompt: `[cloudshell-user@ip-xxx ~]$`

### Step 2: Create the CloudFormation Template

**Copy and paste this entire block** into CloudShell and press Enter:

```bash
cat > template.yaml << 'TEMPLATE_EOF'
AWSTemplateFormatVersion: '2010-09-09'
Description: 'Complete AWS Project Setup - VPC, EC2, RDS, S3, ALB with Docker'

Parameters:
  KeyPairName:
    Description: Name of an existing EC2 KeyPair
    Type: String
    Default: key-0e7e39471a6f908f1
  
  DBPassword:
    Description: Password for RDS database (min 8 characters)
    Type: String
    NoEcho: true
    Default: MyPassword123
    MinLength: 8
    MaxLength: 41
    AllowedPattern: '[a-zA-Z0-9]*'

  YourIPAddress:
    Description: Your IP address for SSH access
    Type: String
    Default: 0.0.0.0/0

Resources:
  MyVPC:
    Type: AWS::EC2::VPC
    Properties:
      CidrBlock: 10.0.0.0/16
      EnableDnsHostnames: true
      EnableDnsSupport: true
      Tags:
        - Key: Name
          Value: MyProject-VPC

  InternetGateway:
    Type: AWS::EC2::InternetGateway
    Properties:
      Tags:
        - Key: Name
          Value: MyProject-IGW

  AttachGateway:
    Type: AWS::EC2::VPCGatewayAttachment
    Properties:
      VpcId: !Ref MyVPC
      InternetGatewayId: !Ref InternetGateway

  PublicSubnet1:
    Type: AWS::EC2::Subnet
    Properties:
      VpcId: !Ref MyVPC
      CidrBlock: 10.0.1.0/24
      AvailabilityZone: !Select [0, !GetAZs '']
      MapPublicIpOnLaunch: true
      Tags:
        - Key: Name
          Value: MyProject-Public-1a

  PublicSubnet2:
    Type: AWS::EC2::Subnet
    Properties:
      VpcId: !Ref MyVPC
      CidrBlock: 10.0.2.0/24
      AvailabilityZone: !Select [1, !GetAZs '']
      MapPublicIpOnLaunch: true
      Tags:
        - Key: Name
          Value: MyProject-Public-1b

  PrivateSubnet1:
    Type: AWS::EC2::Subnet
    Properties:
      VpcId: !Ref MyVPC
      CidrBlock: 10.0.3.0/24
      AvailabilityZone: !Select [0, !GetAZs '']
      Tags:
        - Key: Name
          Value: MyProject-Private-1a

  PrivateSubnet2:
    Type: AWS::EC2::Subnet
    Properties:
      VpcId: !Ref MyVPC
      CidrBlock: 10.0.4.0/24
      AvailabilityZone: !Select [1, !GetAZs '']
      Tags:
        - Key: Name
          Value: MyProject-Private-1b

  PublicRouteTable:
    Type: AWS::EC2::RouteTable
    Properties:
      VpcId: !Ref MyVPC
      Tags:
        - Key: Name
          Value: MyProject-Public-RT

  PublicRoute:
    Type: AWS::EC2::Route
    DependsOn: AttachGateway
    Properties:
      RouteTableId: !Ref PublicRouteTable
      DestinationCidrBlock: 0.0.0.0/0
      GatewayId: !Ref InternetGateway

  SubnetRouteTableAssociation1:
    Type: AWS::EC2::SubnetRouteTableAssociation
    Properties:
      SubnetId: !Ref PublicSubnet1
      RouteTableId: !Ref PublicRouteTable

  SubnetRouteTableAssociation2:
    Type: AWS::EC2::SubnetRouteTableAssociation
    Properties:
      SubnetId: !Ref PublicSubnet2
      RouteTableId: !Ref PublicRouteTable

  LoadBalancerSecurityGroup:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupName: MyProject-LB-SG
      GroupDescription: Security group for Load Balancer
      VpcId: !Ref MyVPC
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 80
          ToPort: 80
          CidrIp: 0.0.0.0/0
        - IpProtocol: tcp
          FromPort: 443
          ToPort: 443
          CidrIp: 0.0.0.0/0
      Tags:
        - Key: Name
          Value: MyProject-LB-SG

  EC2SecurityGroup:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupName: MyProject-EC2-SG
      GroupDescription: Security group for EC2 instances
      VpcId: !Ref MyVPC
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 80
          ToPort: 80
          SourceSecurityGroupId: !Ref LoadBalancerSecurityGroup
        - IpProtocol: tcp
          FromPort: 3000
          ToPort: 3000
          SourceSecurityGroupId: !Ref LoadBalancerSecurityGroup
        - IpProtocol: tcp
          FromPort: 22
          ToPort: 22
          CidrIp: !Ref YourIPAddress
      Tags:
        - Key: Name
          Value: MyProject-EC2-SG

  RDSSecurityGroup:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupName: MyProject-RDS-SG
      GroupDescription: Security group for RDS
      VpcId: !Ref MyVPC
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 3306
          ToPort: 3306
          SourceSecurityGroupId: !Ref EC2SecurityGroup
      Tags:
        - Key: Name
          Value: MyProject-RDS-SG

  S3Bucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub 'myproject-storage-${AWS::AccountId}'
      PublicAccessBlockConfiguration:
        BlockPublicAcls: false
        BlockPublicPolicy: false
        IgnorePublicAcls: false
        RestrictPublicBuckets: false
      VersioningConfiguration:
        Status: Enabled

  S3BucketPolicy:
    Type: AWS::S3::BucketPolicy
    Properties:
      Bucket: !Ref S3Bucket
      PolicyDocument:
        Statement:
          - Sid: PublicReadGetObject
            Effect: Allow
            Principal: '*'
            Action: 's3:GetObject'
            Resource: !Sub '${S3Bucket.Arn}/*'

  DBSubnetGroup:
    Type: AWS::RDS::DBSubnetGroup
    Properties:
      DBSubnetGroupName: myproject-db-subnet-group
      DBSubnetGroupDescription: Subnet group for RDS
      SubnetIds:
        - !Ref PrivateSubnet1
        - !Ref PrivateSubnet2

  RDSDatabase:
    Type: AWS::RDS::DBInstance
    Properties:
      DBInstanceIdentifier: myproject-db
      DBName: myprojectdb
      Engine: mysql
      EngineVersion: '8.0.35'
      DBInstanceClass: db.t3.micro
      AllocatedStorage: 20
      StorageType: gp2
      MasterUsername: admin
      MasterUserPassword: !Ref DBPassword
      VPCSecurityGroups:
        - !Ref RDSSecurityGroup
      DBSubnetGroupName: !Ref DBSubnetGroup
      PubliclyAccessible: false
      BackupRetentionPeriod: 7

  WebUIInstance:
    Type: AWS::EC2::Instance
    Properties:
      ImageId: !Sub '{{resolve:ssm:/aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp2/ami-id}}'
      InstanceType: t2.micro
      KeyName: !Ref KeyPairName
      NetworkInterfaces:
        - AssociatePublicIpAddress: true
          DeviceIndex: 0
          SubnetId: !Ref PublicSubnet1
          GroupSet:
            - !Ref EC2SecurityGroup
      UserData:
        Fn::Base64: !Sub |
          #!/bin/bash
          apt update
          apt upgrade -y
          apt install docker.io -y
          systemctl start docker
          systemctl enable docker
          usermod -aG docker ubuntu
          
          mkdir -p /home/ubuntu/webapp
          cat > /home/ubuntu/webapp/index.html << 'EOF'
          <!DOCTYPE html>
          <html>
          <head>
              <title>My AWS Project</title>
              <style>
                  body { font-family: Arial; text-align: center; padding: 50px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
                  .container { background: white; padding: 40px; border-radius: 15px; max-width: 700px; margin: 0 auto; box-shadow: 0 10px 30px rgba(0,0,0,0.3); }
                  h1 { color: #FF9900; }
              </style>
          </head>
          <body>
              <div class="container">
                  <h1>🚀 My AWS Project - Web UI</h1>
                  <p><strong>Status:</strong> Running with Docker on EC2</p>
                  <p><strong>Region:</strong> EU-West-1</p>
              </div>
          </body>
          </html>
          EOF
          
          cat > /home/ubuntu/webapp/Dockerfile << 'EOF'
          FROM ubuntu:22.04
          RUN apt update && apt upgrade -y && apt install apache2 -y
          COPY index.html /var/www/html/index.html
          EXPOSE 80
          CMD ["apachectl", "-D", "FOREGROUND"]
          EOF
          
          cd /home/ubuntu/webapp
          docker build -t webapp .
          docker run -d -p 80:80 --name webapp --restart always webapp
      Tags:
        - Key: Name
          Value: MyProject-Web-UI

  APIInstance:
    Type: AWS::EC2::Instance
    Properties:
      ImageId: !Sub '{{resolve:ssm:/aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp2/ami-id}}'
      InstanceType: t2.micro
      KeyName: !Ref KeyPairName
      NetworkInterfaces:
        - AssociatePublicIpAddress: true
          DeviceIndex: 0
          SubnetId: !Ref PublicSubnet2
          GroupSet:
            - !Ref EC2SecurityGroup
      UserData:
        Fn::Base64: !Sub |
          #!/bin/bash
          apt update
          apt upgrade -y
          apt install docker.io -y
          systemctl start docker
          systemctl enable docker
          usermod -aG docker ubuntu
          
          mkdir -p /home/ubuntu/api
          cat > /home/ubuntu/api/server.js << 'EOF'
          const http = require('http');
          const server = http.createServer((req, res) => {
            res.statusCode = 200;
            res.setHeader('Content-Type', 'application/json');
            res.end(JSON.stringify({
              message: 'API Server Running!',
              status: 'ok',
              timestamp: new Date().toISOString()
            }, null, 2));
          });
          server.listen(3000, '0.0.0.0');
          EOF
          
          cat > /home/ubuntu/api/Dockerfile << 'EOF'
          FROM node:18-alpine
          WORKDIR /app
          COPY server.js .
          EXPOSE 3000
          CMD ["node", "server.js"]
          EOF
          
          cd /home/ubuntu/api
          docker build -t api .
          docker run -d -p 3000:3000 --name api --restart always api
      Tags:
        - Key: Name
          Value: MyProject-API

  ApplicationLoadBalancer:
    Type: AWS::ElasticLoadBalancingV2::LoadBalancer
    Properties:
      Name: MyProject-ALB
      Scheme: internet-facing
      Type: application
      Subnets:
        - !Ref PublicSubnet1
        - !Ref PublicSubnet2
      SecurityGroups:
        - !Ref LoadBalancerSecurityGroup

  WebTargetGroup:
    Type: AWS::ElasticLoadBalancingV2::TargetGroup
    Properties:
      Name: MyProject-Web-TG
      Port: 80
      Protocol: HTTP
      VpcId: !Ref MyVPC
      HealthCheckPath: /
      Targets:
        - Id: !Ref WebUIInstance

  APITargetGroup:
    Type: AWS::ElasticLoadBalancingV2::TargetGroup
    Properties:
      Name: MyProject-API-TG
      Port: 3000
      Protocol: HTTP
      VpcId: !Ref MyVPC
      HealthCheckPath: /
      Targets:
        - Id: !Ref APIInstance

  WebListener:
    Type: AWS::ElasticLoadBalancingV2::Listener
    Properties:
      LoadBalancerArn: !Ref ApplicationLoadBalancer
      Port: 80
      Protocol: HTTP
      DefaultActions:
        - Type: forward
          TargetGroupArn: !Ref WebTargetGroup

Outputs:
  LoadBalancerDNS:
    Value: !GetAtt ApplicationLoadBalancer.DNSName
  WebUIURL:
    Value: !Sub 'http://${ApplicationLoadBalancer.DNSName}'
  APIURL:
    Value: !Sub 'http://${APIInstance.PublicIp}:3000'
  RDSEndpoint:
    Value: !GetAtt RDSDatabase.Endpoint.Address
  S3BucketName:
    Value: !Ref S3Bucket
  WebUIInstanceIP:
    Value: !GetAtt WebUIInstance.PublicIp
  APIInstanceIP:
    Value: !GetAtt APIInstance.PublicIp
TEMPLATE_EOF
```

✅ Press Enter. You should see: `template.yaml created`

### Step 3: Deploy the Stack

**Copy and paste this command** and press Enter:

```bash
aws cloudformation create-stack \
  --stack-name MyAWSProject \
  --template-body file://template.yaml \
  --parameters \
    ParameterKey=KeyPairName,ParameterValue=key-0e7e39471a6f908f1 \
    ParameterKey=DBPassword,ParameterValue=MyPassword123 \
    ParameterKey=YourIPAddress,ParameterValue=0.0.0.0/0 \
  --region eu-west-1
```

**💡 Optional: Change the password:**
- Replace `MyPassword123` with your own password (8+ characters, letters and numbers only)

You'll see output like:
```json
{
    "StackId": "arn:aws:cloudformation:eu-west-1:123456789:stack/MyAWSProject/..."
}
```

✅ **Success!** Stack creation has started!

### Step 4: Monitor Progress

**Check stack status** (run this command):
```bash
aws cloudformation describe-stacks \
  --stack-name MyAWSProject \
  --region eu-west-1 \
  --query 'Stacks[0].StackStatus' \
  --output text
```

**Keep running this every 1-2 minutes** until you see: `CREATE_COMPLETE`

You'll see status progression:
- `CREATE_IN_PROGRESS` ⏳ (wait...)
- `CREATE_COMPLETE` ✅ (done!)

**Or watch in real-time:**
```bash
watch -n 10 'aws cloudformation describe-stacks --stack-name MyAWSProject --region eu-west-1 --query "Stacks[0].StackStatus" --output text'
```
(Press Ctrl+C to stop watching)

⏱️ **Wait 10-15 minutes for everything to be created**

### Step 5: Get Your URLs

Once status is `CREATE_COMPLETE`, **get all your URLs:**

```bash
aws cloudformation describe-stacks \
  --stack-name MyAWSProject \
  --region eu-west-1 \
  --query 'Stacks[0].Outputs' \
  --output table
```

You'll see a nice table with:
```
---------------------------------------------------------------------------
|                              DescribeStacks                              |
+------------------+-------------------------------------------------------+
|  LoadBalancerDNS | MyProject-ALB-123456.eu-west-1.elb.amazonaws.com     |
|  WebUIURL        | http://MyProject-ALB-123456.eu-west-1.elb.amazonaws.com |
|  APIURL          | http://54.123.45.67:3000                               |
|  RDSEndpoint     | myproject-db.abc123.eu-west-1.rds.amazonaws.com       |
|  S3BucketName    | myproject-storage-123456789                            |
|  WebUIInstanceIP | 54.123.45.67                                           |
|  APIInstanceIP   | 34.98.76.54                                            |
+------------------+-------------------------------------------------------+
```

**Copy the WebUIURL** and open it in your browser! 🎉

---

## 🧪 TEST YOUR APPLICATION

### Test Web UI:
```bash
# Get the Web UI URL
aws cloudformation describe-stacks \
  --stack-name MyAWSProject \
  --region eu-west-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`WebUIURL`].OutputValue' \
  --output text
```
Copy the URL and open in browser. Wait 2-3 minutes for Docker to start.

### Test API:
```bash
# Get the API URL
aws cloudformation describe-stacks \
  --stack-name MyAWSProject \
  --region eu-west-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`APIURL`].OutputValue' \
  --output text
```
Copy and open in browser - you should see JSON response.

### Test with curl (in CloudShell):
```bash
# Test Web UI
curl $(aws cloudformation describe-stacks --stack-name MyAWSProject --region eu-west-1 --query 'Stacks[0].Outputs[?OutputKey==`WebUIURL`].OutputValue' --output text)

# Test API
curl $(aws cloudformation describe-stacks --stack-name MyAWSProject --region eu-west-1 --query 'Stacks[0].Outputs[?OutputKey==`APIURL`].OutputValue' --output text)
```

---

## 📦 UPLOAD FILE TO S3

### From CloudShell:
```bash
# Get bucket name
BUCKET=$(aws cloudformation describe-stacks \
  --stack-name MyAWSProject \
  --region eu-west-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`S3BucketName`].OutputValue' \
  --output text)

# Create a test file
echo "Hello from AWS CloudShell!" > test.txt

# Upload to S3
aws s3 cp test.txt s3://$BUCKET/

# Make it public
aws s3api put-object-acl --bucket $BUCKET --key test.txt --acl public-read

# Get the URL
echo "https://$BUCKET.s3.eu-west-1.amazonaws.com/test.txt"
```

Open the URL in browser to see your file!

---

## 🗄️ TEST RDS DATABASE

### SSH from CloudShell to EC2:
```bash
# Get Web UI instance IP
INSTANCE_IP=$(aws cloudformation describe-stacks \
  --stack-name MyAWSProject \
  --region eu-west-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`WebUIInstanceIP`].OutputValue' \
  --output text)

# SSH to instance (you'll need your .pem file uploaded to CloudShell first)
# See section below about uploading key file
```

### Upload your key file to CloudShell:
1. In CloudShell, click **Actions** → **Upload file**
2. Select your `key-0e7e39471a6f908f1.pem` file
3. Then run:
```bash
chmod 400 key-0e7e39471a6f908f1.pem

ssh -i key-0e7e39471a6f908f1.pem ubuntu@$INSTANCE_IP

# Once connected, install MySQL client
sudo apt update
sudo apt install mysql-client -y

# Get RDS endpoint from CloudFormation outputs page
mysql -h [RDS-ENDPOINT] -u admin -p
# Password: MyPassword123 (or whatever you set)
```

---

## 🧹 DELETE EVERYTHING

### When you're done, delete the entire stack:
```bash
aws cloudformation delete-stack \
  --stack-name MyAWSProject \
  --region eu-west-1
```

**Check deletion status:**
```bash
aws cloudformation describe-stacks \
  --stack-name MyAWSProject \
  --region eu-west-1 \
  --query 'Stacks[0].StackStatus' \
  --output text
```

You'll see:
- `DELETE_IN_PROGRESS` ⏳
- Stack will disappear when complete ✅

**⚠️ Note:** If deletion fails because S3 bucket has files:
```bash
# Empty the bucket first
BUCKET=$(aws cloudformation describe-stacks --stack-name MyAWSProject --region eu-west-1 --query 'Stacks[0].Outputs[?OutputKey==`S3BucketName`].OutputValue' --output text)
aws s3 rm s3://$BUCKET --recursive

# Then delete stack again
aws cloudformation delete-stack --stack-name MyAWSProject --region eu-west-1
```

---

## 🎯 USEFUL COMMANDS

### List all stacks:
```bash
aws cloudformation list-stacks --region eu-west-1 --query 'StackSummaries[?StackStatus!=`DELETE_COMPLETE`].[StackName,StackStatus]' --output table
```

### Get all EC2 instances:
```bash
aws ec2 describe-instances \
  --region eu-west-1 \
  --filters "Name=tag:Name,Values=MyProject*" \
  --query 'Reservations[*].Instances[*].[Tags[?Key==`Name`].Value|[0],PublicIpAddress,State.Name]' \
  --output table
```

### Get Load Balancer DNS:
```bash
aws elbv2 describe-load-balancers \
  --region eu-west-1 \
  --query 'LoadBalancers[?LoadBalancerName==`MyProject-ALB`].DNSName' \
  --output text
```

### Get RDS endpoint:
```bash
aws rds describe-db-instances \
  --region eu-west-1 \
  --db-instance-identifier myproject-db \
  --query 'DBInstances[0].Endpoint.Address' \
  --output text
```

### List S3 bucket contents:
```bash
BUCKET=$(aws cloudformation describe-stacks --stack-name MyAWSProject --region eu-west-1 --query 'Stacks[0].Outputs[?OutputKey==`S3BucketName`].OutputValue' --output text)
aws s3 ls s3://$BUCKET/
```

---

## 📸 TAKING SCREENSHOTS FOR DOCUMENTATION

After deployment, take screenshots of:

1. **CloudFormation Console** - showing CREATE_COMPLETE status
2. **Outputs tab** - showing all URLs
3. **EC2 Console** - showing both instances running
4. **VPC Console** - showing your VPC and subnets
5. **RDS Console** - showing database available
6. **S3 Console** - showing bucket with files
7. **Load Balancer Console** - showing ALB active
8. **Browser** - showing Web UI page
9. **Browser** - showing API JSON response
10. **CloudShell terminal** - showing successful commands

---

## 🎓 ADVANTAGES OF CLOUDSHELL METHOD

✅ **No local software needed** - Everything in browser
✅ **AWS CLI pre-installed** - No setup required
✅ **Credentials automatic** - Already logged in
✅ **Free to use** - No charges for CloudShell
✅ **Commands reusable** - Copy-paste ready
✅ **Works anywhere** - Just need a browser
✅ **Version controlled** - Template is code

---

## 🆘 TROUBLESHOOTING

### If CloudShell doesn't open:
- Check you're in EU-West-1 region
- Try refreshing the browser
- Clear browser cache
- Try incognito/private mode

### If stack creation fails:
```bash
# Check for errors
aws cloudformation describe-stack-events \
  --stack-name MyAWSProject \
  --region eu-west-1 \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`].[LogicalResourceId,ResourceStatusReason]' \
  --output table
```

### If key pair doesn't exist:
Make sure `key-0e7e39471a6f908f1` exists:
```bash
aws ec2 describe-key-pairs --region eu-west-1 --key-names key-0e7e39471a6f908f1
```

### If you need to update the stack:
```bash
aws cloudformation update-stack \
  --stack-name MyAWSProject \
  --template-body file://template.yaml \
  --region eu-west-1
```

---

## 📊 COST REMINDER

- CloudShell: **FREE**
- VPC: **FREE**
- 2 × t2.micro EC2: ~$17/month
- db.t3.micro RDS: ~$12/month
- Load Balancer: ~$16/month
- S3: First 5GB free

**Total: ~$45-50/month** (Free tier: ~$16/month)

**💡 Remember to DELETE the stack when done to avoid charges!**

---

## ✅ SUMMARY

1. Open CloudShell
2. Create template (copy-paste)
3. Deploy stack (1 command)
4. Wait 10-15 minutes
5. Get URLs
6. Test everything
7. Take screenshots
8. Delete when done

**Total time: 15 minutes to full deployment!** 🚀
