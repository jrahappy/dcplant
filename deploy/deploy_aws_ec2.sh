#!/bin/bash

# AWS EC2 Deployment Script for DCPlant
# Run this script on your EC2 instance after initial setup

set -e

echo "🚀 Starting DCPlant deployment on AWS EC2..."

# Update system packages
echo "📦 Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# Install required packages
echo "📦 Installing required packages..."
sudo apt-get install -y \
    docker.io \
    docker-compose \
    nginx \
    certbot \
    python3-certbot-nginx \
    git \
    postgresql-client

# Start and enable Docker
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER

# Clone or pull the repository
if [ -d "/home/ubuntu/dcplant" ]; then
    echo "📂 Updating existing repository..."
    cd /home/ubuntu/dcplant
    git pull origin main
else
    echo "📂 Cloning repository..."
    cd /home/ubuntu
    git clone https://github.com/yourusername/dcplant.git
    cd dcplant
fi

# Copy environment file
if [ ! -f ".env.production" ]; then
    echo "⚙️ Creating environment file..."
    cp .env.production.example .env.production
    echo "⚠️ Please edit .env.production with your actual values!"
    read -p "Press enter after editing .env.production..."
fi

# Build and start Docker containers
echo "🐳 Building Docker containers..."
sudo docker-compose -f docker-compose.yml build

echo "🐳 Starting Docker containers..."
sudo docker-compose -f docker-compose.yml up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 10

# Run database migrations
echo "🗄️ Running database migrations..."
sudo docker-compose exec web python manage.py migrate

# Create superuser
echo "👤 Creating superuser..."
sudo docker-compose exec web python manage.py createsuperuser

# Collect static files
echo "📁 Collecting static files..."
sudo docker-compose exec web python manage.py collectstatic --noinput

# Setup SSL with Let's Encrypt (optional)
read -p "Do you want to setup SSL with Let's Encrypt? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "Enter your domain name: " domain_name
    sudo certbot --nginx -d $domain_name -d www.$domain_name
fi

# Setup CloudWatch monitoring (optional)
echo "📊 Setting up CloudWatch monitoring..."
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i amazon-cloudwatch-agent.deb
rm amazon-cloudwatch-agent.deb

# Create backup script
cat > /home/ubuntu/backup_dcplant.sh << 'EOF'
#!/bin/bash
# Backup script for DCPlant
BACKUP_DIR="/home/ubuntu/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Backup database
docker-compose exec -T db pg_dump -U dcplant_user dcplant | gzip > $BACKUP_DIR/db_backup_$DATE.sql.gz

# Backup media files
tar -czf $BACKUP_DIR/media_backup_$DATE.tar.gz -C /home/ubuntu/dcplant media/

# Keep only last 7 days of backups
find $BACKUP_DIR -type f -mtime +7 -delete

echo "Backup completed: $DATE"
EOF

chmod +x /home/ubuntu/backup_dcplant.sh

# Setup cron job for daily backups
(crontab -l 2>/dev/null; echo "0 2 * * * /home/ubuntu/backup_dcplant.sh >> /home/ubuntu/backup.log 2>&1") | crontab -

echo "✅ Deployment completed successfully!"
echo ""
echo "📝 Next steps:"
echo "1. Edit .env.production with your actual configuration"
echo "2. Access your application at http://your-ec2-ip"
echo "3. Configure your domain DNS to point to this EC2 instance"
echo "4. Setup SSL certificate with Let's Encrypt"
echo "5. Configure AWS Security Groups to allow HTTP/HTTPS traffic"
echo ""
echo "🔧 Useful commands:"
echo "- View logs: sudo docker-compose logs -f"
echo "- Restart services: sudo docker-compose restart"
echo "- Stop services: sudo docker-compose down"
echo "- Backup database: ./backup_dcplant.sh"