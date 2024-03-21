import logging


class StructuredLogger(logging.Logger):
    def _log(
        self,
        level,
        msg,
        args,
        exc_info=None,
        extra=None,
        stack_info=False,
        stacklevel=1,
    ):
        if isinstance(msg, dict):
            structured_msg = " | ".join(f"{key}={value}" for key, value in msg.items())
            super()._log(
                level, structured_msg, args, exc_info, extra, stack_info, stacklevel
            )
        else:
            super()._log(level, msg, args, exc_info, extra, stack_info, stacklevel)
