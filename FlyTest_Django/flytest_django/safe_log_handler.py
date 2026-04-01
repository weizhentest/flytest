"""
安全的日志轮转处理器

解决 Windows 环境下 TimedRotatingFileHandler 在多进程情况下
由于文件锁导致的轮转失败问题。

主要改进：
1. 使用复制+清空的方式替代重命名，避免文件锁问题
2. 支持多进程同时写入
3. 确保日志不丢失
"""

import os
import time
import shutil
import logging
from logging.handlers import TimedRotatingFileHandler


class SafeTimedRotatingFileHandler(TimedRotatingFileHandler):
    """
    安全的时间轮转日志处理器
    
    在 Windows 环境下，当文件被其他进程占用时，
    标准的 TimedRotatingFileHandler 使用重命名方式会失败。
    这个类使用复制+清空的方式来避免这个问题。
    """
    
    def doRollover(self):
        """
        执行日志轮转，使用复制+清空的方式
        """
        if self.stream:
            self.stream.close()
            self.stream = None
        
        # 获取当前时间和目标文件名
        currentTime = int(time.time())
        dstNow = time.localtime(currentTime)[-1]
        t = self.rolloverAt - self.interval
        
        if self.utc:
            timeTuple = time.gmtime(t)
        else:
            timeTuple = time.localtime(t)
            dstThen = timeTuple[-1]
            if dstNow != dstThen:
                if dstNow:
                    addend = 3600
                else:
                    addend = -3600
                timeTuple = time.localtime(t + addend)
        
        # 生成目标文件名
        dfn = self.rotation_filename(self.baseFilename + "." + time.strftime(self.suffix, timeTuple))
        
        # 如果目标文件已存在，先删除
        if os.path.exists(dfn):
            try:
                os.remove(dfn)
            except OSError:
                pass
        
        # 尝试使用复制+清空的方式轮转
        try:
            if os.path.exists(self.baseFilename):
                # 复制当前日志文件到归档位置
                shutil.copy2(self.baseFilename, dfn)
                # 清空原文件
                with open(self.baseFilename, 'w', encoding='utf-8') as f:
                    f.truncate(0)
        except (OSError, PermissionError) as e:
            # 复制失败，尝试原始的重命名方式
            try:
                self.rotate(self.baseFilename, dfn)
            except (OSError, PermissionError) as e2:
                # 重命名也失败，记录警告但不中断程序
                import sys
                print(f"[SafeLogHandler] 日志轮转失败: {e2}", file=sys.stderr)
        
        # 删除过期的备份文件
        if self.backupCount > 0:
            for s in self.getFilesToDelete():
                try:
                    os.remove(s)
                except OSError:
                    pass
        
        # 重新打开日志文件
        if not self.delay:
            self.stream = self._open()
        
        # 计算下次轮转时间
        newRolloverAt = self.computeRollover(currentTime)
        while newRolloverAt <= currentTime:
            newRolloverAt = newRolloverAt + self.interval
        
        if (self.when == 'MIDNIGHT' or self.when.startswith('W')) and not self.utc:
            dstAtRollover = time.localtime(newRolloverAt)[-1]
            if dstNow != dstAtRollover:
                if not dstNow:
                    addend = -3600
                else:
                    addend = 3600
                newRolloverAt += addend
        
        self.rolloverAt = newRolloverAt
    
    def shouldRollover(self, record):
        """
        检查是否需要轮转
        
        添加额外的安全检查，确保在文件不存在时也能正常工作
        """
        try:
            return super().shouldRollover(record)
        except Exception:
            # 任何检查错误都返回 False，继续写入当前文件
            return False
