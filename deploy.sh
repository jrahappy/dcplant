#!/bin/bash

# DCPlant Quick Deployment Script
# This script helps deploy DCPlant to various platforms

set -e

echo "🦷 DCPlant Deployment Tool"
echo "=========================="
echo ""

# Function to display menu
show_menu() {
    echo "Select deployment target:"
    echo "1) Local Docker"
    echo "2) AWS EC2"
    echo "3) AWS ECS/Fargate"
    echo "4) Heroku"
    echo "5) DigitalOcean"
    echo "6) Azure"
    echo "7) Google Cloud"
    echo "8) Exit"
    echo ""
    read -p "Enter choice [1-8]: " choice
}

# Local Docker deployment
deploy_local() {
    echo "🐳 Deploying to Local Docker..."
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        echo "❌ Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    # Copy environment file if not exists
    if [ ! -f ".env.production" ]; then
        cp .env.production.example .env.production
        echo "⚠️ Created .env.production - Please edit with your values"
        read -p "Press enter after editing .env.production..."
    fi
    
    # Build and start containers
    docker-compose build
    docker-compose up -d
    
    # Run migrations
    docker-compose exec web python manage.py migrate
    
    echo "✅ Local deployment complete!"
    echo "Access at: http://localhost"
}

# AWS EC2 deployment
deploy_aws_ec2() {
    echo "☁️ Deploying to AWS EC2..."
    
    read -p "Enter EC2 instance IP: " ec2_ip
    read -p "Enter SSH key path: " ssh_key
    
    # Copy files to EC2
    scp -i $ssh_key -r ./* ubuntu@$ec2_ip:/home/ubuntu/dcplant/
    
    # Run deployment script on EC2
    ssh -i $ssh_key ubuntu@$ec2_ip "cd /home/ubuntu/dcplant && chmod +x deploy/deploy_aws_ec2.sh && ./deploy/deploy_aws_ec2.sh"
    
    echo "✅ AWS EC2 deployment complete!"
    echo "Access at: http://$ec2_ip"
}

# Heroku deployment
deploy_heroku() {
    echo "🚀 Deploying to Heroku..."
    
    # Check if Heroku CLI is installed
    if ! command -v heroku &> /dev/null; then
        echo "❌ Heroku CLI is not installed. Please install it first."
        exit 1
    fi
    
    read -p "Enter Heroku app name: " app_name
    
    # Create Heroku app
    heroku create $app_name
    
    # Add addons
    heroku addons:create heroku-postgresql:mini
    heroku addons:create heroku-redis:mini
    
    # Set environment variables
    heroku config:set DJANGO_SETTINGS_MODULE=core.settings.production
    heroku config:set SECRET_KEY=$(openssl rand -base64 32)
    
    # Deploy
    git push heroku main
    
    # Run migrations
    heroku run python manage.py migrate
    
    echo "✅ Heroku deployment complete!"
    echo "Access at: https://$app_name.herokuapp.com"
}

# DigitalOcean deployment
deploy_digitalocean() {
    echo "🌊 Deploying to DigitalOcean..."
    
    read -p "Enter Droplet IP: " droplet_ip
    
    # SSH and deploy
    ssh root@$droplet_ip << 'ENDSSH'
        # Install Docker if not exists
        if ! command -v docker &> /dev/null; then
            curl -fsSL https://get.docker.com -o get-docker.sh
            sh get-docker.sh
            apt install -y docker-compose
        fi
        
        # Clone or update repository
        if [ -d "/opt/dcplant" ]; then
            cd /opt/dcplant
            git pull origin main
        else
            cd /opt
            git clone https://github.com/yourusername/dcplant.git
            cd dcplant
        fi
        
        # Deploy
        docker-compose up -d
        docker-compose exec web python manage.py migrate
ENDSSH
    
    echo "✅ DigitalOcean deployment complete!"
    echo "Access at: http://$droplet_ip"
}

# Main script
clear
show_menu

case $choice in
    1)
        deploy_local
        ;;
    2)
        deploy_aws_ec2
        ;;
    3)
        echo "Please use AWS Console or CLI for ECS deployment"
        echo "Task definition available at: deploy/deploy_aws_ecs.yml"
        ;;
    4)
        deploy_heroku
        ;;
    5)
        deploy_digitalocean
        ;;
    6)
        echo "Please use Azure Portal or CLI for deployment"
        echo "See DEPLOYMENT.md for Azure instructions"
        ;;
    7)
        echo "Please use Google Cloud Console or gcloud CLI"
        echo "See DEPLOYMENT.md for GCP instructions"
        ;;
    8)
        echo "Goodbye!"
        exit 0
        ;;
    *)
        echo "Invalid option. Please try again."
        ;;
esac

echo ""
echo "📚 For detailed instructions, see DEPLOYMENT.md"
echo "❓ For help, visit: https://github.com/yourusername/dcplant/issues"