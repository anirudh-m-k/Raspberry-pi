# Host Fintrack Boutique on Raspberry Pi

Here are the complete steps to deploy the application on your Raspberry Pi.

## 1. System Preparation
Update your system and install necessary packages.
```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y python3-pip nginx
```
## 2. Project Setup
Move project files to your home directory and set up the environment.
```bash
cd ~/Finance-Track
python3 -m venv ~/python-env
source ~/python-env/bin/activate
pip install -r requirements.txt
pip install gunicorn
```
## 3. Setup Notification Scripts
Create these scripts first for automated alerts.

**Discord Notify Script** (`/usr/local/bin/discord-notify.sh`)
```bash
#!/bin/bash
WEBHOOK_URL="https://discordapp.com/api/webhooks/YOUR_WEBHOOK_URL_HERE"
TITLE="Raspberry Pi"
MESSAGE="$1"

if [ "$2" = "with-ip" ]; then
  LOCAL_IP=$(ip route get 1 | awk '{print $7; exit}')
  MESSAGE="${MESSAGE}\n\n**Local IP**\n${LOCAL_IP}"
fi

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
PAYLOAD="{\"embeds\": [{\"title\": \"$TITLE\", \"description\": \"$MESSAGE\", \"color\": 65280, \"footer\": {\"text\": \"System Notification\"}, \"timestamp\": \"$TIMESTAMP\"}]}"
curl -s -X POST "$WEBHOOK_URL" -H "Content-Type: application/json" -d "$PAYLOAD" > /dev/null
```
*Run:* `sudo chmod +x /usr/local/bin/discord-notify.sh`

**Internet Notify Service** (`/etc/systemd/system/internet-online-notify.service`)
```ini
[Unit]
Description=Notify when Internet is available
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStartPre=/bin/sleep 15
ExecStart=/usr/local/bin/discord-notify.sh "✅ Internet is reachable" with-ip

[Install]
WantedBy=multi-user.target
```
*Run:* `sudo systemctl enable internet-online-notify`

**Cloudflare Healthcheck Script** (`/usr/local/bin/cloudflare-healthcheck.sh`)
*(Create this before creating the Cloudflare setup)*
```bash
#!/bin/bash

URL="https://fintrack.dpdns.org/login"
STATE_FILE="/tmp/fintrack_health_state"

# The Cloudflare tunnel needs a few seconds to connect to the edge network.
# First wait 10 seconds, then check up to 6 times (every 5 seconds) for a 200 OK.
sleep 10
STATUS="000"
for i in {1..6}; do
    STATUS=$(curl -o /dev/null -s -w "%{http_code}" "$URL")
    if [ "$STATUS" = "200" ]; then
        break
    fi
    # Wait 5 seconds before checking again
    sleep 5
done

PREVIOUS_STATUS=""
[ -f "$STATE_FILE" ] && PREVIOUS_STATUS=$(cat "$STATE_FILE")

# Only notify if status changed
if [ "$STATUS" != "$PREVIOUS_STATUS" ]; then

    if [ "$STATUS" = "200" ]; then
        /usr/local/bin/discord-notify.sh "✅ Fintrack Boutique endpoint reachable (HTTP 200)"
    else
        /usr/local/bin/discord-notify.sh "❌ Fintrack Boutique endpoint DOWN (HTTP $STATUS)"
    fi

    echo "$STATUS" > "$STATE_FILE"
fi
```
*Run:* `sudo chmod +x /usr/local/bin/cloudflare-healthcheck.sh`

## 4. Configure Gunicorn Service
Create `/etc/systemd/system/fintrack-gunicorn.service`:
```ini
[Unit]
Description=Fintrack Boutique - Gunicorn Service
After=network.target internet-online-notify.service

[Service]
Type=simple
User=anirudh
ExecStartPre=/bin/sleep 10
Group=www-data
WorkingDirectory=/home/anirudh/Finance-Track
Environment="PATH=/home/anirudh/python-env/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/home/anirudh/python-env/bin/gunicorn --bind 127.0.0.1:8000 run:app
ExecStartPost=-/usr/local/bin/discord-notify.sh "🚀 Gunicorn started successfully"
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
*Run:*
```bash
sudo systemctl daemon-reload
sudo systemctl enable fintrack-gunicorn
sudo systemctl start fintrack-gunicorn
```
## 5. Configure Nginx
Create `/etc/nginx/sites-available/fintrack`:
```nginx
server {
    listen 80;
    server_name fintrack.dpdns.org; 

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
*Run:*
```bash
sudo ln -s /etc/nginx/sites-available/fintrack /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

**Add Nginx Notification Hook**:
Create directory first:
`sudo mkdir -p /etc/systemd/system/nginx.service.d`

Create `/etc/systemd/system/nginx.service.d/notify.conf`:
```ini
[Unit]
After=internet-online-notify.service

[Service]
ExecStartPre=/bin/sleep 10
ExecStartPost=-/usr/local/bin/discord-notify.sh "🌐 Nginx started successfully"
```
*Run:* `sudo systemctl daemon-reload && sudo systemctl restart nginx`

## 6. Cloudflare Tunnel Setup

### Part A: Local Machine (Laptop)
Run these steps on your laptop to generate the certificate.

1.  **Install Cloudflared**:
    Download the appropriate `.deb` package for your local machine's architecture from [Cloudflare Downloads](<https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/>)
    ```bash
    # Example for amd64 (use appropriate package for your machine)
    wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
    sudo dpkg -i cloudflared-linux-amd64.deb
    ```

2.  **Authenticate**:
    ```bash
    cloudflared tunnel login
    ```

3.  **Transfer Certificate to Pi**:
    Replace `<local_ip>` with your Raspberry Pi's local IP address.
    ```bash
    scp ~/.cloudflared/cert.pem anirudh@<local_ip>:/tmp/
    ```

### Part B: Raspberry Pi
1. Install and move certificate:
```bash
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-armhf.deb
sudo dpkg -i cloudflared-linux-armhf.deb
mkdir -p ~/.cloudflared
sudo mv /tmp/cert.pem ~/.cloudflared/cert.pem
```

2. Create Tunnel & Route:
```bash
cloudflared tunnel create fintrack-app
# (Copy UUID from output)
cloudflared tunnel route dns fintrack-app fintrack.dpdns.org
```

3. Configure Config (`/etc/cloudflared/config.yml`):
Create directory first:
`sudo mkdir -p /etc/cloudflared`

```yaml
tunnel: <UUID>
credentials-file: /etc/cloudflared/<UUID>.json
ingress:
  - hostname: fintrack.dpdns.org
    service: http://127.0.0.1:80
  - service: http_status:404
```

Move the credentials file to the config directory (replace <UUID> with the actual UUID from above):
```bash
sudo cp ~/.cloudflared/<UUID>.json /etc/cloudflared/
```

4. Create Service (`/etc/systemd/system/cloudflared.service`):
```ini
[Unit]
Description=Cloudflared Tunnel
After=network-online.target nginx.service fintrack-gunicorn.service
Wants=network-online.target
Requires=nginx.service fintrack-gunicorn.service

[Service]
Type=simple
ExecStartPre=/bin/sleep 15
ExecStart=/usr/bin/cloudflared tunnel --config /etc/cloudflared/config.yml run fintrack-app
Restart=always
RestartSec=5
ExecStartPost=-/usr/local/bin/cloudflare-healthcheck.sh

[Install]
WantedBy=multi-user.target
```
*Run:* `sudo systemctl enable cloudflared --now`

## 7. Performance (Swap)
Optimize for Pi Zero/3 RAM.
`/etc/sysctl.d/99-swappiness.conf`:
```ini
vm.swappiness=10
```
*Run:* `sudo sysctl -p /etc/sysctl.d/99-swappiness.conf`

## 8. Add WWW Subdomain (Optional)
To also make `www.fintrack.dpdns.org` accessible and point to your app, run the following steps:

1. **Create the DNS Route:**
You can do this via the command line:
```bash
cloudflared tunnel route dns fintrack-app www.fintrack.dpdns.org
```
*OR via the Cloudflare Dashboard:* 
Go to your domain's **DNS** settings and add a new record:
- **Type:** `CNAME`
- **Name:** `www`
- **Target:** `<UUID>.cfargotunnel.com` (Replace with your actual Tunnel UUID)
- **Proxy status:** Proxied (Orange Cloud)

2. **Update Cloudflare Config:**
Edit `sudo nano /etc/cloudflared/config.yml` and add the `www` hostname to your ingress list *before* the 404 rule:
```yaml
ingress:
  - hostname: fintrack.dpdns.org
    service: http://127.0.0.1:80
  - hostname: www.fintrack.dpdns.org
    service: http://127.0.0.1:80
  - service: http_status:404
```

3. **Update Nginx Config:**
Edit `sudo nano /etc/nginx/sites-available/fintrack` to include the `www` subdomain in the `server_name` directive:
```nginx
server_name fintrack.dpdns.org www.fintrack.dpdns.org;
```

4. **Restart Services:**
```bash
sudo systemctl restart nginx cloudflared
```
