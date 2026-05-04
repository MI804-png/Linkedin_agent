# How to Upload the CloudFormation Template

## Method 1: Upload via CloudFormation Console (EASIEST)

1. **Download the file**: `cloudformation-template.yaml` (already in your c:\aws folder)

2. **Go to AWS Console**: https://console.aws.amazon.com

3. **Switch to EU-West-1 region** (top-right corner)

4. **Open CloudFormation**:
   - Search for "CloudFormation" in the search bar
   - Click **CloudFormation** service

5. **Create Stack**:
   - Click **Create stack** button
   - Select **With new resources (standard)**

6. **Upload Template**:
   - Choose **Upload a template file**
   - Click **Choose file**
   - Select `cloudformation-template.yaml` from your computer
   - Click **Next**

7. **Configure Stack**:
   - **Stack name**: `MyAWSProject`
   - **Parameters**:
     - KeyPairName: `key-0e7e39471a6f908f1` (already filled)
     - DBPassword: `MyPassword123` (or change it)
     - YourIPAddress: `0.0.0.0/0` (or your IP)
   - Click **Next**

8. **Configure Stack Options**:
   - Leave everything as default
   - Click **Next**

9. **Review**:
   - Scroll down
   - Click **Submit**

10. **Wait 10-15 minutes** for `CREATE_COMPLETE`

11. **Get URLs**:
    - Click **Outputs** tab
    - Copy the WebUIURL and open in browser!

---

## Method 2: Upload via CloudShell

1. **Open CloudShell** in AWS Console (top navigation bar, click `>_` icon)

2. **Upload the file**:
   - Click **Actions** → **Upload file**
   - Select `cloudformation-template.yaml` from your computer
   - Wait for upload to complete

3. **Deploy**:
```bash
aws cloudformation create-stack \
  --stack-name MyAWSProject \
  --template-body file://cloudformation-template.yaml \
  --parameters \
    ParameterKey=KeyPairName,ParameterValue=key-0e7e39471a6f908f1 \
    ParameterKey=DBPassword,ParameterValue=MyPassword123 \
    ParameterKey=YourIPAddress,ParameterValue=0.0.0.0/0 \
  --region eu-west-1
```

4. **Check status**:
```bash
aws cloudformation describe-stacks \
  --stack-name MyAWSProject \
  --region eu-west-1 \
  --query 'Stacks[0].StackStatus' \
  --output text
```

5. **Get URLs when done**:
```bash
aws cloudformation describe-stacks \
  --stack-name MyAWSProject \
  --region eu-west-1 \
  --query 'Stacks[0].Outputs' \
  --output table
```

---

## 🎯 RECOMMENDED: Use Method 1 (Console Upload)
It's the easiest - just point and click!

The file `cloudformation-template.yaml` is ready in your `c:\aws` folder.
