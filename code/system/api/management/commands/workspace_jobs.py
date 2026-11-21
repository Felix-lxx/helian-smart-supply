import time
from django.core.management.base import BaseCommand
from django.db import close_old_connections
from api.workspace_jobs import run_due_jobs


class Command(BaseCommand):
    help='独立检查超时预留、报价有效期和到货提醒，不依赖浏览器打开。'
    def add_arguments(self,parser):
        parser.add_argument('--once',action='store_true')
        parser.add_argument('--interval',type=int,default=45)
    def handle(self,*args,**options):
        while True:
            close_old_connections()
            try:self.stdout.write(str(run_due_jobs()))
            except Exception as exc:
                self.stderr.write(f'任务本轮失败：{type(exc).__name__}: {exc}')
                if options['once']:raise
            if options['once']:return
            time.sleep(max(10,options['interval']))
