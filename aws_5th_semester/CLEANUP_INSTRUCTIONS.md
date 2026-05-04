# AWS Resources Cleanup Instructions

**IMPORTANT:** To avoid ongoing charges, follow these steps to delete all resources.

## Option 1: Delete CloudFormation Stack (Recommended - Easiest)

This will automatically delete ALL resources created by the stack:

### Steps:
1. Go to **AWS Console** → Search for **"CloudFormation"**
2. Select your stack: **MyAWSProject**
3. Click **"Delete"** button
4. Confirm deletion
5. Wait 5-10 minutes for deletion to complete

**This will automatically delete:**
- ✓ EC2 Instances (both Web and API)
- ✓ Load Balancer
- ✓ Target Groups
- ✓ RDS Database
- ✓ Security Groups
- ✓ VPC and Subnets
- ✓ All networking components

## Option 2: Manual Deletion (Only if CloudFormation fails)

If CloudFormation deletion fails, manually delete in this order:

### 1. Delete Load Balancer
```
AWS Console → EC2 → Load Balancers → Select MyProject-ALB → Actions → Delete
```

### 2. Delete Target Groups
```
AWS Console → EC2 → Target Groups → Select both target groups → Actions → Delete
```

### 3. Terminate EC2 Instances
```
AWS Console → EC2 → Instances → Select both instances → Instance State → Terminate
```

### 4. Delete RDS Database
```
AWS Console → RDS → Databases → Select myproject-db → Actions → Delete
⚠️ UNCHECK "Create final snapshot" to delete immediately
```

### 5. Delete VPC (will cascade delete subnets, route tables, etc.)
```
AWS Console → VPC → Your VPCs → Select vpc-01d140e788ae1d7f2 → Actions → Delete VPC
```

### 6. Empty and Delete S3 Bucket
```
AWS Console → S3 → myproject-storage-674182808760 → Empty → Delete
```

## What Gets Charged (If Left Running)

| Service | Approximate Cost (After Free Tier) |
|---------|-----------------------------------|
| EC2 t3.micro (2 instances) | ~$15/month |
| RDS db.t3.micro | ~$15/month |
| Application Load Balancer | ~$16/month |
| S3 Storage | ~$0.50/month |
| Data Transfer | Variable |
| **TOTAL** | **~$46/month** |

## Free Tier Limits

If you're within AWS Free Tier (first 12 months):
- **EC2:** 750 hours/month of t2.micro or t3.micro (covers 1 instance)
- **RDS:** 750 hours/month of db.t3.micro Single-AZ
- **S3:** 5 GB storage
- **Data Transfer:** 15 GB/month

⚠️ **You have 2 EC2 instances**, so you'll still be charged for the second one even in Free Tier!

## Recommendation

**To completely avoid charges:**
1. **Delete the CloudFormation stack NOW** (Option 1 above)
2. Verify all resources are deleted in AWS Console
3. Check your billing dashboard in 24 hours

**If you need the project again later:**
- You have the CloudFormation template saved
- You have all application code documented
- You can redeploy in minutes using the same template

## Verification Steps After Deletion

After deleting, verify these are gone:

```bash
# Check EC2 instances
aws ec2 describe-instances --region eu-west-1

# Check RDS databases
aws rds describe-db-instances --region eu-west-1

# Check Load Balancers
aws elbv2 describe-load-balancers --region eu-west-1

# Check CloudFormation stacks
aws cloudformation describe-stacks --region eu-west-1
```

All should return empty results or "stack not found" errors.

---

**Bottom Line:** Delete the CloudFormation stack **MyAWSProject** to avoid all charges. Takes 2 minutes to delete, saves ~$46/month.
