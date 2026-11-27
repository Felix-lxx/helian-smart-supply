"""Explicitly simulated device telemetry for integration demos; no model inference."""
import os
import random
import time

import requests


def main():
    token = os.getenv('DEVICE_INGEST_TOKEN', '')
    if not token:
        raise SystemExit('请先设置 DEVICE_INGEST_TOKEN，与后端进程的环境变量一致。')
    url = os.getenv('DEVICE_REPORT_URL', 'http://127.0.0.1:8000/api/device/report/')
    print('演示设备 MOCK-RDK-X5-01：上报随机模拟遥测，不执行视觉推理。Ctrl+C 停止。')
    while True:
        payload = {
            'device_id': 'MOCK-RDK-X5-01',
            'npu_load': random.randint(45, 85),
            'yolo_delay': random.randint(12, 28),
            'warning_msg': '演示遥测 · 随机模拟值，非真实设备数据',
        }
        try:
            response = requests.post(url, json=payload, headers={'X-Device-Token': token}, timeout=5)
            response.raise_for_status()
            print(f"[模拟上报] 负载 {payload['npu_load']}% / 延迟 {payload['yolo_delay']}ms")
        except requests.RequestException as exc:
            print(f'上报失败：{exc}')
        time.sleep(3)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n演示设备已停止。')
