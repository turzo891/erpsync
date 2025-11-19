# Quick Start Guide - ERP Sync

Get up and running in 5 minutes!

## Choose Your Method

### Option A: Docker (Recommended - Easiest!)

```bash
cd /Users/spoofing/Documents/erpsync

# Configure credentials
cp .env.example .env
nano .env  # Add your ERP API credentials

# Run setup script
./docker-run.sh
```

**That's it!** See [DOCKER.md](DOCKER.md) for more details.

---

### Option B: Native Python

## Step 1: Install Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install packages
pip install -r requirements.txt
```

## Step 2: Get Your API Credentials

### From Cloud ERP (AWS):
1. Login to your cloud ERPNext
2. Click your profile picture → **API Access**
3. Click **Generate Keys**
4. Copy **API Key** and **API Secret**

### From Local ERP:
1. Login to your local ERPNext
2. Click your profile picture → **API Access**
3. Click **Generate Keys**
4. Copy **API Key** and **API Secret**

## Step 3: Configure Environment

```bash
# Copy the example file
cp .env.example .env

# Edit .env and add your credentials
nano .env  # or use any text editor
```

Replace these values in `.env`:
```
CLOUD_ERP_URL=https://your-cloud-erp.com
CLOUD_API_KEY=paste_your_cloud_key_here
CLOUD_API_SECRET=paste_your_cloud_secret_here

LOCAL_ERP_URL=http://localhost:8000
LOCAL_API_KEY=paste_your_local_key_here
LOCAL_API_SECRET=paste_your_local_secret_here

WEBHOOK_SECRET=change_this_to_random_string_123456
```

## Step 4: Initialize and Test

```bash
# Initialize database
python main.py init

# Test connections
python main.py test
```

You should see:
```
[OK] Connected to Cloud
[OK] Connected to Local
[OK] All connections successful
```

## Step 5: Choose Your Sync Method

### Option A: Manual Sync (Easiest to Start)

```bash
# Do initial sync of all data
python main.py sync

# Or sync specific DocType
python main.py sync --doctype Customer
```

### Option B: Real-time Sync with Webhooks

```bash
# 1. Start the webhook server
python main.py webhook
```

**In another terminal**, set up webhooks:

```bash
# 2. Follow the setup instructions
python main.py setup-webhook
```

This will show you what to configure in both ERPs.

## Step 6: Test It!

1. **Create a new Customer** in your Cloud ERP
2. **Check your Local ERP** - the customer should appear!
3. **Edit the Customer** in Local ERP
4. **Check Cloud ERP** - changes should sync back!

## Monitor Sync Status

```bash
# Check sync status anytime
python main.py status

# View any conflicts
python main.py conflicts
```

## Common Issues

### "Connection failed"
- Check your ERP URLs are accessible
- Verify API credentials are correct
- Ensure both ERPs are running

### "Webhook not working"
- Make sure webhook server is running
- Check webhook URL is accessible from ERP
- Verify webhook secret matches in both places

### "Permission denied"
- Make sure API keys have sufficient permissions
- In ERPNext, go to User → check "API Access" is enabled

## What's Next?

- Edit `config.yaml` to add more DocTypes to sync
- Set up as a background service (see README.md)
- Configure conflict resolution strategy
- Set up monitoring

## Need Help?

Check the full README.md for detailed documentation!
