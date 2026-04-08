import uuid
import logging
from yookassa import Configuration, Payment
from config import settings

logger = logging.getLogger(__name__)

# Configure YooKassa
if settings.YOOKASSA_SHOP_ID and settings.YOOKASSA_SECRET_KEY:
    Configuration.account_id = settings.YOOKASSA_SHOP_ID
    Configuration.secret_key = settings.YOOKASSA_SECRET_KEY
else:
    logger.warning("YooKassa credentials are not fully configured in settings.")

class YooKassaService:
    @staticmethod
    async def create_payment(amount: float, description: str, metadata: dict, return_url: str):
        """
        Create a YooKassa payment.
        
        Args:
            amount: Payment amount in RUB.
            description: Payment description.
            metadata: Custom data to attach to the payment.
            return_url: URL to redirect the user after payment.
            
        Returns:
            The payment object if successful, None otherwise.
        """
        try:
            idempotency_key = str(uuid.uuid4())
            payment = Payment.create({
                "amount": {
                    "value": str(amount),
                    "currency": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": return_url
                },
                "capture": True,
                "description": description,
                "metadata": metadata
            }, idempotency_key)
            
            return payment
        except Exception as e:
            logger.error(f"Failed to create YooKassa payment: {e}", exc_info=True)
            return None

    @staticmethod
    async def check_payment_status(payment_id: str):
        """
        Check the status of a YooKassa payment.
        
        Args:
            payment_id: The ID of the payment to check.
            
        Returns:
            The payment object if successful, None otherwise.
        """
        try:
            payment = Payment.find_one(payment_id)
            return payment
        except Exception as e:
            logger.error(f"Failed to check YooKassa payment status: {e}", exc_info=True)
            return None
