import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler
from app.core.config import settings

log_dir = os.path.join(settings.BASE_DIR, "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "app.log")
error_log_file = os.path.join(log_dir, "error.log")
chat_log_file = os.path.join(log_dir, "chat.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        TimedRotatingFileHandler(log_file, when='midnight', interval=1, backupCount=30, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

error_handler = TimedRotatingFileHandler(error_log_file, when='midnight', interval=1, backupCount=30, encoding='utf-8')
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

chat_handler = TimedRotatingFileHandler(chat_log_file, when='midnight', interval=1, backupCount=30, encoding='utf-8')
chat_handler.setLevel(logging.INFO)
chat_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))

logger = logging.getLogger("gov_tech_ai")
logger.addHandler(error_handler)

chat_logger = logging.getLogger("chat")
chat_logger.addHandler(chat_handler)
chat_logger.setLevel(logging.INFO)
chat_logger.propagate = False

def log_chat_request(user_message: str, project_type: str, file_name: str = None):
    chat_logger.info(f"USER INPUT | project_type={project_type} | file={file_name} | message={user_message}")

def log_chat_response(answer: str, sources_count: int, processing_time: float):
    chat_logger.info(f"AI RESPONSE START | sources={sources_count} | time={processing_time:.2f}s\n{answer}\nAI RESPONSE END")

def log_error(error_type: str, error_message: str, details: str = None):
    logger.error(f"ERROR [{error_type}] | {error_message}" + (f" | Details: {details}" if details else ""))

def log_feedback(feedback_type: str, message_index: int, user_message: str = None, ai_response: str = None, project_type: str = None, is_cancel: bool = False):
    feedback_emoji = "👍" if feedback_type == "like" else "👎"
    cancel_text = " [CANCELLED]" if is_cancel else ""
    chat_logger.info(f"FEEDBACK {feedback_emoji}{cancel_text} | type={feedback_type} | index={message_index} | project_type={project_type} | is_cancel={is_cancel}")
    if user_message:
        chat_logger.info(f"FEEDBACK USER | {user_message[:500]}")
    if ai_response:
        chat_logger.info(f"FEEDBACK AI | {ai_response[:2000]}")
