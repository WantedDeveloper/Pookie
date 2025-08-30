#!/bin/bash

# === CONFIG ===
BOT_NAME="Pookiebot"                      # service name
BOT_DIR="/root/Pookie"                    # repo directory
BOT_MAIN="main.py"                       # main bot file
PYTHON_BIN="/usr/bin/python3"            # check with: which python3
GIT_REPO="https://github.com/WantedDeveloper/Pookie.git"

SERVICE_PATH="/etc/systemd/system/$BOT_NAME.service"

setup_service() {
  echo "🔄 Setting up $BOT_NAME service..."

  # Clone repo if not already there
  if [ ! -d "$BOT_DIR" ]; then
    echo "📥 Cloning repo..."
    git clone $GIT_REPO $BOT_DIR
  fi

  # Ensure pip is installed
  echo "📦 Installing pip..."
  apt update -y
  apt install -y python3-pip

  # Install requirements
  cd $BOT_DIR || exit
  if [ -f "requirements.txt" ]; then
    echo "📦 Installing requirements..."
    pip3 install --upgrade -r requirements.txt
  else
    echo "⚠️ requirements.txt not found, cannot install dependencies!"
  fi

  # Create systemd service
  sudo bash -c "cat > $SERVICE_PATH" <<EOL
[Unit]
Description=Telegram Bot - $BOT_NAME
After=network.target

[Service]
User=root
WorkingDirectory=$BOT_DIR
ExecStart=$PYTHON_BIN $BOT_MAIN
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOL

  echo "✅ Reloading systemd..."
  sudo systemctl daemon-reload
  sudo systemctl enable $BOT_NAME
  sudo systemctl restart $BOT_NAME

  echo "🎉 Bot is now running 24/7!"
  echo "👉 To check logs: journalctl -u $BOT_NAME -f"
}

update_bot() {
  echo "📥 Checking for updates..."
  cd $BOT_DIR || exit

  if [ -d ".git" ]; then
    git fetch origin
    LOCAL=$(git rev-parse HEAD)
    REMOTE=$(git rev-parse origin/main 2>/dev/null || git rev-parse origin/master 2>/dev/null)

    if [ "$LOCAL" != "$REMOTE" ]; then
      echo "🔄 Updates found! Pulling..."
      git pull origin main || git pull origin master

      echo "📦 Re-installing requirements..."
      if [ -f "requirements.txt" ]; then
        pip3 install --upgrade -r requirements.txt
      fi

      echo "🔁 Restarting bot..."
      sudo systemctl restart $BOT_NAME
      echo "✅ Bot updated & restarted!"
    else
      echo "👌 No updates found, skipping restart."
    fi
  else
    echo "⚠️ No git repo found in $BOT_DIR"
  fi
}

case "$1" in
  update)
    update_bot
    ;;
  *)
    setup_service
    ;;
esac
