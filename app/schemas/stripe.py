from pydantic import BaseModel
from typing import Optional


class GetCustomerRequest(BaseModel):
    """Request model for getting/creating a Stripe customer"""
    email: Optional[str] = None


class GetCustomerResponse(BaseModel):
    """Response model for Stripe customer operations"""
    customer_id: str
    created: bool = False  # True if customer was newly created, False if existing
    message: str


class CancelSubscriptionRequest(BaseModel):
    """Request model for canceling a subscription"""
    user_id: str


class CancelSubscriptionResponse(BaseModel):
    """Response model for subscription cancellation"""
    subscription_id: str
    status: str
    canceled_at: str
    message: str


class UpdateSubscriptionRequest(BaseModel):
    """Request model for updating a subscription"""
    user_id: str
    new_price_id: Optional[str] = None
    quantity: Optional[int] = None
    proration_behavior: Optional[str] = "none"  # create_prorations, none, always_invoice


class UpdateSubscriptionResponse(BaseModel):
    """Response model for subscription updates"""
    subscription_id: str
    status: str
    message: str


class GetSubscriptionInfoRequest(BaseModel):
    """Request model for getting subscription info"""
    user_id: str


class PendingUpdate(BaseModel):
    """Model for pending subscription updates"""
    new_plan_name: Optional[str] = None
    new_price: Optional[float] = None
    effective_date: str  # Format: MM/DD/YYYY
    currency: str


class GetSubscriptionInfoResponse(BaseModel):
    """Response model for subscription info"""
    subscription_id: str
    status: str
    renewal_date: str  # Format: MM/DD/YYYY
    price: float
    currency: str
    plan_name: Optional[str] = None
    cancel_at_period_end: bool
    has_pending_update: bool = False
    pending_update: Optional[PendingUpdate] = None
    message: str


class WebhookResponse(BaseModel):
    """Response model for webhook processing"""
    received: bool
    event_type: str
    processed: bool
    message: str


class GetSessionInfoRequest(BaseModel):
    """Request model for getting session info"""
    session_id: str


class GetSessionInfoResponse(BaseModel):
    """Response model for session info"""
    session_id: str
    payment_status: str
    is_paid: bool
    message: str


class DeleteCustomerRequest(BaseModel):
    """Request model for deleting a customer"""
    user_id: str


class DeleteCustomerResponse(BaseModel):
    """Response model for customer deletion"""
    user_id: str
    stripe_deleted: bool
    firestore_deleted: bool
    message: str


class RenewSubscriptionRequest(BaseModel):
    """Request model for renewing a subscription"""
    user_id: str


class RenewSubscriptionResponse(BaseModel):
    """Response model for subscription renewal"""
    subscription_id: str
    status: str
    current_period_end: str
    message: str
