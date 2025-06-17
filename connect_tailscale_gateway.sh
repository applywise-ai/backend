#!/bin/bash
echo "🔗 Connecting to Tailscale gateway to complete setup..."
ssh -i ~/.ssh/applywise-tailscale.pem ec2-user@54.221.97.225
