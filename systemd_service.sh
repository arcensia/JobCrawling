#!/bin/bash
# systemd 서비스 관리 스크립트 (AWS 서버용)

SERVICE_NAME="job_bot"
SERVICE_FILE="$(dirname "$0")/job_bot.service"
SYSTEMD_DIR="/etc/systemd/system"

case "$1" in
    install)
        echo "=== systemd 서비스 설치 ==="
        cp "$SERVICE_FILE" "$SYSTEMD_DIR/"
        systemctl daemon-reload
        systemctl enable "$SERVICE_NAME"
        systemctl start "$SERVICE_NAME"
        echo "✓ 설치 완료"
        echo ""
        echo "사용법:"
        echo "  systemctl status $SERVICE_NAME"
        echo "  systemctl restart $SERVICE_NAME"
        echo "  journalctl -u $SERVICE_NAME -f"
        ;;
    start)
        systemctl start "$SERVICE_NAME"
        echo "✓ 서비스 시작됨"
        ;;
    stop)
        systemctl stop "$SERVICE_NAME"
        echo "✓ 서비스 중지됨"
        ;;
    restart)
        systemctl restart "$SERVICE_NAME"
        echo "✓ 서비스 재시작됨"
        ;;
    status)
        systemctl status "$SERVICE_NAME" --no-pager -l
        ;;
    logs)
        journalctl -u "$SERVICE_NAME" -f
        ;;
    uninstall)
        echo "=== 서비스 제거 ==="
        systemctl stop "$SERVICE_NAME" 2>/dev/null
        systemctl disable "$SERVICE_NAME" 2>/dev/null
        rm -f "$SYSTEMD_DIR/$SERVICE_NAME.service"
        systemctl daemon-reload
        echo "✓ 제거 완료"
        ;;
    *)
        echo "사용법: $0 {install|start|stop|restart|status|logs|uninstall}"
        ;;
esac
