from fastapi import APIRouter, HTTPException, Depends, Request
import stripe
import logging
from ...schemas.stripe import (
    GetCustomerRequest, 
    GetCustomerResponse,
    CancelSubscriptionRequest,
    CancelSubscriptionResponse,
    UpdateSubscriptionRequest,
    UpdateSubscriptionResponse,
    GetSubscriptionInfoRequest,
    GetSubscriptionInfoResponse,
    PendingUpdate,
    GetSessionInfoRequest,
    GetSessionInfoResponse,
    DeleteCustomerRequest,
    DeleteCustomerResponse,
    RenewSubscriptionRequest,
    RenewSubscriptionResponse,
    WebhookResponse
)
from ...db.firestore import firestore_manager
from ...core.config import settings
from ..dependencies import get_user_id

router = APIRouter()
logger = logging.getLogger(__name__)

# Stripe is initialized globally in app/__init__.py

# Disable Stripe internal INFO logging
stripe.log = logging.getLogger("stripe")
stripe.log.setLevel(logging.WARNING)
stripe.log.addHandler(logging.StreamHandler())

@router.post("/customer", response_model=GetCustomerResponse)
async def get_or_create_customer(
    request: GetCustomerRequest,
    user_id: str = Depends(get_user_id)
):
    """
    Get or create a Stripe customer ID for a user.
    
    This endpoint:
    1. Checks the Firestore stripe_customers table for an existing customer ID
    2. If found, returns the existing customer ID
    3. If not found, creates a new Stripe customer and stores the ID in Firestore
    4. Returns the customer ID
    """
    try:
        logger.info(f"Processing customer request for user: {user_id}")
        
        # Check if customer already exists in Firestore
        existing_customer = firestore_manager.get_stripe_customer(user_id)
        
        if existing_customer:
            logger.info(f"Found existing customer: {existing_customer}")
            return GetCustomerResponse(
                customer_id=existing_customer,
                created=False,
                message="Retrieved existing customer ID"
            )
        
        # Create new Stripe customer
        customer_data = {
            "metadata": {"user_id": user_id}
        }
        
        # Add email if provided
        if request.email:
            customer_data["email"] = request.email
        
        stripe_customer = stripe.Customer.create(**customer_data)

        # Store customer ID in Firestore
        firestore_manager.store_stripe_customer(user_id, stripe_customer.id)
        
        logger.info(f"Created and stored new customer: {stripe_customer.id}")
        
        return GetCustomerResponse(
            customer_id=stripe_customer.id,
            created=True,
            message="Created new customer ID"
        )
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe API error: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Stripe error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error processing customer request: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while processing customer request"
        )


@router.post("/subscription/cancel", response_model=CancelSubscriptionResponse)
async def cancel_subscription(
    request: CancelSubscriptionRequest,
    user_id: str = Depends(get_user_id)
):
    """
    Cancel a customer's subscription at the end of the current period.
    
    This endpoint:
    1. Gets the active subscription ID from Firestore
    2. Cancels the subscription in Stripe at period end
    3. Updates the subscription status in Firestore
    4. Returns the cancellation details
    """
    try:
        logger.info(f"Processing subscription cancellation for user: {user_id}")
        
        # Get active subscription ID from Firestore
        subscription_id = firestore_manager.get_active_subscription_id(user_id)
        
        if not subscription_id:
            raise HTTPException(
                status_code=404,
                detail="No active subscription found for user"
            )
        
        logger.info(f"Found active subscription: {subscription_id}")
        
        # Get subscription details to check if it has a schedule
        current_subscription = stripe.Subscription.retrieve(subscription_id)
        schedule_id = current_subscription.get('schedule')
        
        if schedule_id:
            # If subscription has a schedule, modify it to remove future phases
            logger.info(f"Subscription has schedule {schedule_id}, modifying to cancel at period end")
            try:
                # Get the existing schedule
                existing_schedule = stripe.SubscriptionSchedule.retrieve(schedule_id)
                
                # Get current period end
                canceled_at_timestamp = current_subscription.get('current_period_end') or current_subscription['items']['data'][0].get('current_period_end')
                
                # Keep current phase, remove future phases
                current_phase = existing_schedule['phases'][0].copy()  # Get the current phase
                current_phase['end_date'] = canceled_at_timestamp  # Set to end at period end
                
                stripe.SubscriptionSchedule.modify(
                    schedule_id,
                    phases=[current_phase],  # Only keep current phase, removes future phases
                    end_behavior="cancel"    # Cancel the subscription when schedule ends
                )
                
                # Format the cancellation date as MM/DD/YYYY
                from datetime import datetime
                canceled_at_date = datetime.fromtimestamp(canceled_at_timestamp)
                formatted_canceled_at = canceled_at_date.strftime("%m/%d/%Y")
                
                logger.info(f"Schedule {schedule_id} modified to end at period end")
                
                return CancelSubscriptionResponse(
                    subscription_id=subscription_id,
                    status=current_subscription['status'],
                    canceled_at=formatted_canceled_at,
                    message="Subscription will be canceled at the end of the current period"
                )
            except stripe.error.StripeError as e:
                logger.error(f"Error modifying subscription schedule: {e}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to modify subscription schedule: {str(e)}"
                )
        else:
            # No schedule, cancel subscription directly
            logger.info("No schedule found, canceling subscription directly")
            subscription = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True
            )
            
            logger.info(f"Subscription {subscription_id} set to cancel at period end")
            
            # Format the cancellation date as MM/DD/YYYY
            from datetime import datetime
            canceled_at_timestamp = subscription.get('current_period_end') or subscription['items']['data'][0].get('current_period_end')
            canceled_at_date = datetime.fromtimestamp(canceled_at_timestamp)
            formatted_canceled_at = canceled_at_date.strftime("%m/%d/%Y")
            
            return CancelSubscriptionResponse(
                subscription_id=subscription_id,
                status=subscription['status'],
                canceled_at=formatted_canceled_at,
                message="Subscription will be canceled at the end of the current period"
            )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except stripe.error.StripeError as e:
        logger.error(f"Stripe API error during cancellation: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Stripe error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error canceling subscription: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while canceling subscription"
        )


@router.post("/subscription/update", response_model=UpdateSubscriptionResponse)
async def update_subscription(
    request: UpdateSubscriptionRequest,
    user_id: str = Depends(get_user_id)
):
    """
    Update a customer's subscription (change plan, quantity, etc.).
    
    This endpoint:
    1. Gets the active subscription ID from Firestore
    2. Updates the subscription in Stripe with new parameters
    3. Returns the updated subscription details
    """
    try:
        logger.info(f"Processing subscription update for user: {user_id}")
        
        # Get active subscription ID from Firestore
        subscription_id = firestore_manager.get_active_subscription_id(user_id)
        
        if not subscription_id:
            raise HTTPException(
                status_code=404,
                detail="No active subscription found for user"
            )
        
        logger.info(f"Found active subscription: {subscription_id}")
        
        # Get current subscription details
        current_subscription = stripe.Subscription.retrieve(subscription_id)
        logger.info(f"Current subscription status: {current_subscription['status']}")
        
        # Check if the update is actually changing anything
        current_item = current_subscription['items']['data'][0]  # Assuming single item subscription
        current_price_id = current_item['price']['id']
        current_quantity = current_item['quantity']
        
        new_price_id = request.new_price_id if request.new_price_id else current_price_id
        new_quantity = request.quantity if request.quantity else current_quantity
        
        # If nothing is changing, return current subscription info
        if new_price_id == current_price_id and new_quantity == current_quantity:
            logger.info("No changes detected - same price and quantity")
            
            # Format the current period end date as MM/DD/YYYY
            from datetime import datetime
            current_period_end_timestamp = current_subscription.get('current_period_end') or current_subscription['items']['data'][0].get('current_period_end')
            current_period_end_date = datetime.fromtimestamp(current_period_end_timestamp)
            formatted_period_end = current_period_end_date.strftime("%m/%d/%Y")
            
            return UpdateSubscriptionResponse(
                subscription_id=subscription_id,
                status=current_subscription['status'],
                schedule_id=None,
                effective_date=None,
                message="No changes needed - subscription already has the requested configuration"
            )
        
        if request.proration_behavior == "none":
            # Use subscription schedule for no proration (change at next billing cycle)
            logger.info("Creating subscription schedule for next billing cycle change")
            
            # Prepare new items for the schedule
            new_items = []
            for item in current_subscription['items']['data']:
                new_item = {
                    "price": new_price_id,
                    "quantity": new_quantity
                }
                new_items.append(new_item)
            
            # Check if subscription already has a schedule
            existing_schedule_id = current_subscription.get('schedule')
            
            if existing_schedule_id:
                # Check if the existing schedule has pending changes
                logger.info(f"Found existing schedule: {existing_schedule_id}")
                try:
                    existing_schedule = stripe.SubscriptionSchedule.retrieve(existing_schedule_id)
                except stripe.error.StripeError as e:
                    logger.error(f"Stripe error retrieving existing schedule: {e}")
                    raise HTTPException(
                        status_code=400,
                        detail=f"Failed to retrieve existing schedule: {str(e)}"
                    )
                
                # If there are multiple phases, there's already a pending change
                if len(existing_schedule['phases']) > 1:
                    logger.warning(f"Schedule {existing_schedule_id} already has pending changes")
                    raise HTTPException(
                        status_code=409,
                        detail="Subscription already has a pending plan change. Please wait for the current change to take effect or cancel it before setting a new one."
                    )
                
                # If only one phase, we can proceed to add the new phase
                logger.info(f"Modifying existing schedule: {existing_schedule_id}")
                schedule_id = existing_schedule_id
            else:
                # Create new subscription schedule
                logger.info("Creating new subscription schedule")
                try:
                    schedule = stripe.SubscriptionSchedule.create(
                        from_subscription=subscription_id
                    )
                    schedule_id = schedule['id']
                except stripe.error.StripeError as e:
                    logger.error(f"Stripe error creating schedule: {e}")
                    raise HTTPException(
                        status_code=400,
                        detail=f"Failed to create subscription schedule: {str(e)}"
                    )
            
            # Get the current period end timestamp
            try:
                current_period_end = current_subscription.get('current_period_end') or current_subscription['items']['data'][0].get('current_period_end')
                current_period_start = current_subscription.get('current_period_start') or current_subscription['items']['data'][0].get('current_period_start')
            except (KeyError, IndexError, TypeError) as e:
                logger.error(f"Error accessing subscription period dates: {e}")
                raise HTTPException(
                    status_code=400,
                    detail="Invalid subscription data structure"
                )
            
            if not current_period_end or not current_period_start:
                raise HTTPException(
                    status_code=400,
                    detail="Unable to determine subscription billing period dates"
                )
 
            # Modify the schedule to add the new phase
            try:
                updated_schedule = stripe.SubscriptionSchedule.modify(
                    schedule_id,
                    phases=[
                        {
                            # Current phase until next billing cycle
                            "items": [
                                {
                                    "price": item['price']['id'],
                                    "quantity": item['quantity']
                                } for item in current_subscription['items']['data']
                            ],
                            "start_date": current_period_start,
                            "end_date": current_period_end
                        },
                        {
                            # New phase starting at next billing cycle (ongoing)
                            "items": new_items,
                            "start_date": current_period_end
                            # No end_date or iterations = continues indefinitely
                        }
                    ],
                    end_behavior="release"  # Release to normal billing after phases complete
                )
            except stripe.error.StripeError as e:
                logger.error(f"Stripe error during schedule modification: {e}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to schedule subscription update: {str(e)}"
                )
            
            logger.info(f"Updated subscription schedule: {schedule_id}")
            
            return UpdateSubscriptionResponse(
                subscription_id=subscription_id,
                status=current_subscription['status'],
                schedule_id=schedule_id,
                message="Subscription scheduled to update on next billing cycle"
            )
        else:
            # Direct subscription update for immediate changes (with proration)
            logger.info("Updating subscription immediately with proration")
            
            update_params = {
                "proration_behavior": request.proration_behavior
            }
            
            if request.new_price_id or request.quantity:
                # Update subscription items
                items = []
                for item in current_subscription['items']['data']:
                    item_update = {"id": item['id']}
                    
                    if request.new_price_id:
                        item_update["price"] = request.new_price_id
                    if request.quantity:
                        item_update["quantity"] = request.quantity
                        
                    items.append(item_update)
                
                update_params["items"] = items
            
            # Update subscription in Stripe
            updated_subscription = stripe.Subscription.modify(
                subscription_id,
                **update_params
            )
            logger.info(f"Updated subscription: {updated_subscription['id']}")
            
            return UpdateSubscriptionResponse(
                subscription_id=subscription_id,
                status=updated_subscription['status'],
                schedule_id=None,
                effective_date=None,
                message="Subscription updated immediately"
            )
        
    except HTTPException:
        # Re-raise HTTP exceptions (like our 409 conflict)
        raise
    except stripe.error.StripeError as e:
        logger.error(f"Stripe API error during update: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Stripe error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error updating subscription: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while updating subscription"
        )


@router.get("/subscription/info", response_model=GetSubscriptionInfoResponse)
async def get_subscription_info(
    user_id: str = Depends(get_user_id)
):
    """
    Get subscription information including renewal date and price.
    
    This endpoint:
    1. Gets the active subscription ID from Firestore
    2. Retrieves subscription details from Stripe
    3. Formats and returns subscription info with renewal date and pricing
    """
    try:
        logger.info(f"Processing subscription info request for user: {user_id}")
        
        # Get active subscription ID from Firestore
        subscription_id = firestore_manager.get_active_subscription_id(user_id)

        if not subscription_id:
            raise HTTPException(
                status_code=404,
                detail="No active subscription found for user"
            )
        
        logger.info(f"Found active subscription: {subscription_id}")
        
        # Get subscription details from Stripe
        subscription = stripe.Subscription.retrieve(subscription_id)
        
        # Get pricing information from the first subscription item
        if not subscription['items']['data']:
            raise HTTPException(
                status_code=400,
                detail="Subscription has no items"
            )
        
        # Get the first item (most subscriptions have one item)
        subscription_item = subscription['items']['data'][0]
        price = subscription_item['price']
        
        # Calculate total price (price * quantity)
        total_price = (price['unit_amount'] / 100) * subscription_item['quantity']  # Convert cents to dollars
        
        # Format renewal date as MM/DD/YYYY
        from datetime import datetime
        renewal_timestamp = subscription_item['current_period_end']
        renewal_date = datetime.fromtimestamp(renewal_timestamp)
        formatted_renewal_date = renewal_date.strftime("%m/%d/%Y")
        
        # Get plan name from price nickname or product name
        plan_name = price.get('nickname')
        if not plan_name and price.get('product'):
            try:
                product = stripe.Product.retrieve(price['product'])
                plan_name = product['name']
            except:
                plan_name = None
        
        # Check for pending updates (schedule changes) and cancellation status
        has_pending_update = False
        pending_update = None
        cancel_at_period_end = subscription['cancel_at_period_end']  # Default from subscription

        # Check if there are any pending updates in the subscription schedule
        try:
            schedule_id = subscription.get('schedule')
            if schedule_id:
                schedule = stripe.SubscriptionSchedule.retrieve(schedule_id)
                
                # Check if schedule has cancellation behavior
                if schedule.get('end_behavior') == 'cancel':
                    cancel_at_period_end = True
                    logger.info(f"Schedule {schedule_id} has end_behavior=cancel, setting cancel_at_period_end=True")
                
                current_phase = None
                next_phase = None
                # Find current and next phases by matching price IDs
                # Get current subscription's price ID
                current_subscription_price_id = subscription['items']['data'][0]['price']['id']
                logger.info(f"Current subscription price ID: {current_subscription_price_id}")
                
                # Since update only allows one plan change, there should be exactly 2 phases
                # Find the current phase and the other one is the next phase
                for i, phase in enumerate(schedule['phases']):
                    if phase['items'] and len(phase['items']) > 0:
                        phase_price_id = phase['items'][0]['price']
                        logger.info(f"Phase {i} price ID: {phase_price_id}")
                        
                        if phase_price_id == current_subscription_price_id:
                            current_phase = phase
                        else:
                            # This is the other phase - the next/pending phase
                            next_phase = phase
                
                # If there's a next phase with different pricing
                if next_phase and current_phase:
                    current_items = current_phase['items']
                    next_items = next_phase['items']
                    
                    if len(current_items) > 0 and len(next_items) > 0:
                        current_price_id = current_items[0]['price']
                        next_price_id = next_items[0]['price']
                        
                        if current_price_id != next_price_id:
                            has_pending_update = True
                            
                            # Get next price details
                            next_price = stripe.Price.retrieve(next_price_id)
                            next_total_price = (next_price['unit_amount'] / 100) * next_items[0]['quantity']
                            
                            # Get next plan name
                            next_plan_name = next_price.get('nickname')
                            if not next_plan_name and next_price.get('product'):
                                try:
                                    next_product = stripe.Product.retrieve(next_price['product'])
                                    next_plan_name = next_product['name']
                                except:
                                    next_plan_name = None
                            
                            # Format effective date
                            effective_timestamp = next_phase['start_date']
                            effective_date = datetime.fromtimestamp(effective_timestamp)
                            formatted_effective_date = effective_date.strftime("%m/%d/%Y")
                            
                            pending_update = PendingUpdate(
                                new_plan_name=next_plan_name,
                                new_price=next_total_price,
                                effective_date=formatted_effective_date,
                                currency=next_price['currency'].upper()
                            )
        except Exception as e:
            logger.warning(f"Could not retrieve pending updates for subscription {subscription_id}: {e}")
            # Continue without pending update info
        
        logger.info(f"Retrieved subscription info for {subscription_id}")
        logger.info(f"Cancel at period end: {cancel_at_period_end}")
        
        return GetSubscriptionInfoResponse(
            subscription_id=subscription_id,
            status=subscription['status'],
            renewal_date=formatted_renewal_date,
            price=total_price,
            currency=price['currency'].upper(),
            plan_name=plan_name,
            cancel_at_period_end=cancel_at_period_end,
            has_pending_update=has_pending_update,
            pending_update=pending_update,
            message="Subscription info retrieved successfully"
        )
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe API error during info retrieval: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Stripe error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error retrieving subscription info: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while retrieving subscription info"
        )


@router.post("/session/info", response_model=GetSessionInfoResponse)
async def get_session_info(
    request: GetSessionInfoRequest,
    user_id: str = Depends(get_user_id)
):
    """
    Get Stripe checkout session information and payment status.
    
    This endpoint:
    1. Retrieves the checkout session from Stripe
    2. Checks the payment status
    3. Returns whether the payment was successful (paid) or not
    """
    try:
        logger.info(f"Processing session info request for session: {request.session_id}")
        
        # Retrieve session from Stripe
        session = stripe.checkout.Session.retrieve(request.session_id)
        
        # Get payment status
        payment_status = session.payment_status
        is_paid = payment_status == 'paid'
        
        logger.info(f"Session {request.session_id} payment status: {payment_status}")
        
        return GetSessionInfoResponse(
            session_id=request.session_id,
            payment_status=payment_status,
            is_paid=is_paid,
            message=f"Session payment status: {payment_status}"
        )
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe API error retrieving session: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Stripe error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error retrieving session info: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while retrieving session info"
        )


@router.delete("/customer", response_model=DeleteCustomerResponse)
async def delete_customer(
    request: DeleteCustomerRequest,
    user_id: str = Depends(get_user_id)
):
    """
    Delete a customer from both Stripe and Firestore.
    
    This endpoint:
    1. Gets the customer ID from Firestore
    2. Deletes the customer from Stripe
    3. Deletes the customer record from Firestore
    4. Returns the deletion status for both operations
    """
    try:
        logger.info(f"Processing customer deletion request for user: {user_id}")
        
        # Get customer ID from Firestore first
        customer_id = firestore_manager.get_stripe_customer(user_id)
        
        stripe_deleted = False
        firestore_deleted = False
        
        # Delete from Stripe if customer exists
        if customer_id:
            try:
                stripe.Customer.delete(customer_id)
                stripe_deleted = True
                logger.info(f"Deleted Stripe customer: {customer_id}")
            except stripe.error.StripeError as e:
                logger.warning(f"Failed to delete Stripe customer {customer_id}: {e}")
                # Continue with Firestore deletion even if Stripe deletion fails
        else:
            logger.warning(f"No Stripe customer ID found for user {user_id}")
        
        # Delete from Firestore
        try:
            firestore_deleted = firestore_manager.delete_stripe_customer(user_id)
        except Exception as e:
            logger.error(f"Failed to delete from Firestore: {e}")
            # Don't raise here, we want to return the status of both operations
        
        # Determine overall success message
        if stripe_deleted and firestore_deleted:
            message = "Customer deleted from both Stripe and Firestore"
        elif stripe_deleted and not firestore_deleted:
            message = "Customer deleted from Stripe, but no Firestore record found"
        elif not stripe_deleted and firestore_deleted:
            message = "Customer deleted from Firestore, but Stripe deletion failed"
        else:
            message = "No customer found in either Stripe or Firestore"
        
        logger.info(f"Customer deletion completed for user {user_id}: Stripe={stripe_deleted}, Firestore={firestore_deleted}")
        
        return DeleteCustomerResponse(
            user_id=user_id,
            stripe_deleted=stripe_deleted,
            firestore_deleted=firestore_deleted,
            message=message
        )
        
    except Exception as e:
        logger.error(f"Error processing customer deletion: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while deleting customer"
        )


@router.post("/subscription/renew", response_model=RenewSubscriptionResponse)
async def renew_subscription(
    request: RenewSubscriptionRequest,
    user_id: str = Depends(get_user_id)
):
    """
    Reactivate a canceled subscription.
    
    This endpoint:
    1. Gets the active subscription ID from Firestore
    2. Checks if the subscription is canceled (cancel_at_period_end=True)
    3. Reactivates the subscription by setting cancel_at_period_end=False
    4. Returns the renewed subscription details
    
    Note: This only works for subscriptions that are canceled but still active
    (i.e., cancel_at_period_end=True but current_period_end hasn't passed yet)
    """
    try:
        logger.info(f"Processing subscription renewal for user: {user_id}")
        
        # Get active subscription ID from Firestore
        subscription_id = firestore_manager.get_active_subscription_id(user_id)
        
        if not subscription_id:
            raise HTTPException(
                status_code=404,
                detail="No active subscription found for user"
            )
        
        logger.info(f"Found subscription: {subscription_id}")
        
        # Get subscription details
        subscription = stripe.Subscription.retrieve(subscription_id)
        
        # Check if subscription is canceled (either directly or via schedule)
        is_canceled = subscription.get('cancel_at_period_end', False)
        schedule_id = subscription.get('schedule')
        schedule_canceled = False
        
        # Check if there's a schedule with cancel behavior
        if schedule_id and not is_canceled:
            logger.info(f"Checking schedule {schedule_id} for cancellation status")
            try:
                schedule = stripe.SubscriptionSchedule.retrieve(schedule_id)
                if schedule.get('end_behavior') == 'cancel':
                    schedule_canceled = True
                    logger.info(f"Schedule {schedule_id} has end_behavior=cancel")
            except stripe.error.StripeError as e:
                logger.warning(f"Could not retrieve schedule {schedule_id}: {e}")
        
        # If neither subscription nor schedule is canceled, no renewal needed
        if not is_canceled and not schedule_canceled:
            logger.info("Subscription is not canceled (neither directly nor via schedule) - no renewal needed")
            raise HTTPException(
                status_code=400,
                detail="Subscription is not canceled - no renewal needed"
            )
        
        # Check if subscription is still active (not expired)
        if subscription['status'] not in ['active', 'trialing']:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot renew subscription with status: {subscription['status']}"
            )
        
        logger.info(f"Reactivating canceled subscription: {subscription_id}")
        
        # Handle reactivation based on cancellation type
        if schedule_canceled and schedule_id:
            # If canceled via schedule, modify the schedule to remove cancel behavior
            logger.info(f"Reactivating by removing cancel behavior from schedule {schedule_id}")
            try:
                # Get the current schedule to preserve its phases
                schedule = stripe.SubscriptionSchedule.retrieve(schedule_id)
                
                # Modify the schedule to remove end_behavior=cancel
                # Keep all existing phases but change end_behavior to release
                stripe.SubscriptionSchedule.modify(
                    schedule_id,
                    end_behavior="release"  # Change from "cancel" to "release"
                )
                logger.info(f"Schedule {schedule_id} end_behavior changed from 'cancel' to 'release'")
                
                # Get the updated subscription
                renewed_subscription = stripe.Subscription.retrieve(subscription_id)
            except stripe.error.StripeError as e:
                logger.error(f"Error modifying schedule {schedule_id}: {e}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to reactivate subscription by modifying schedule: {str(e)}"
                )
        else:
            # If canceled directly, modify subscription
            logger.info("Reactivating by setting cancel_at_period_end=False")
            renewed_subscription = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=False
            )
        
        logger.info(f"Subscription {subscription_id} successfully renewed")
        
        # Format the current period end date as MM/DD/YYYY
        from datetime import datetime
        current_period_end_timestamp = renewed_subscription.get('current_period_end') or renewed_subscription['items']['data'][0].get('current_period_end')
        current_period_end_date = datetime.fromtimestamp(current_period_end_timestamp)
        formatted_period_end = current_period_end_date.strftime("%m/%d/%Y")
        
        return RenewSubscriptionResponse(
            subscription_id=subscription_id,
            status=renewed_subscription['status'],
            current_period_end=formatted_period_end,
            message="Subscription successfully renewed and will continue billing"
        )
        
    except HTTPException:
        raise
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error during renewal: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Stripe error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error renewing subscription: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while renewing subscription"
        )


@router.post("/webhook", response_model=WebhookResponse)
async def handle_stripe_webhook(request: Request):
    """
    Handle Stripe webhook events to update subscription data in Firestore.
    
    Supported events:
    - checkout.session.completed: Store subscription ID on first checkout
    - invoice.payment_succeeded: Record successful renewals
    - invoice.payment_failed: Mark subscription as at risk
    - customer.subscription.updated: Update subscription status and plan changes
    - customer.subscription.deleted: Handle cancelled subscriptions
    """
    try:
        # Get the raw body and signature
        body = await request.body()
        signature = request.headers.get('stripe-signature')
        
        if not signature:
            raise HTTPException(status_code=400, detail="Missing Stripe signature")
        
        if not settings.STRIPE_WEBHOOK_SECRET:
            logger.error("Stripe webhook secret not configured")
            raise HTTPException(status_code=500, detail="Webhook secret not configured")

        # Verify the webhook signature
        try:
            event = stripe.Webhook.construct_event(
                body, signature, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid payload")
        except stripe.error.SignatureVerificationError:
            raise HTTPException(status_code=400, detail="Invalid signature")

        event_type = event['type']
        event_data = event['data']['object']
        
        logger.info(f"Processing Stripe webhook event: {event_type}")
        
        # Route to appropriate handler
        if event_type == 'checkout.session.completed':
            await handle_checkout_completed(event_data)
        elif event_type == 'invoice.payment_succeeded':
            await handle_payment_succeeded(event_data)
        elif event_type == 'invoice.payment_failed':
            await handle_payment_failed(event_data)
        elif event_type == 'customer.subscription.updated':
            await handle_subscription_updated(event_data)
        elif event_type == 'customer.subscription.deleted':
            await handle_subscription_deleted(event_data)
        else:
            logger.info(f"Unhandled webhook event type: {event_type}")
            return WebhookResponse(
                received=True,
                event_type=event_type,
                processed=False,
                message=f"Event type {event_type} not handled"
            )
        
        return WebhookResponse(
            received=True,
            event_type=event_type,
            processed=True,
            message=f"Successfully processed {event_type} event"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while processing webhook"
        )


async def handle_checkout_completed(session_data):
    """Handle checkout.session.completed - store subscription ID and set pro status"""
    try:
        customer_id = session_data.get('customer')
        subscription_id = session_data.get('subscription')
        
        if not customer_id or not subscription_id:
            logger.warning("Checkout session missing customer or subscription ID")
            return
        
        # Find user by customer ID
        user_id = firestore_manager.get_user_by_customer_id(customer_id)
        if not user_id:
            logger.warning(f"No user found for customer ID: {customer_id}")
            return
        
        # Store subscription ID
        firestore_manager.update_subscription_id(user_id, subscription_id)
        
        # Set user as pro member
        firestore_manager.set_pro_member_status(user_id, True)
        
        logger.info(f"Stored subscription {subscription_id} and set pro status for user {user_id}")
        
    except Exception as e:
        logger.error(f"Error handling checkout completed: {e}")
        raise


async def handle_payment_succeeded(invoice_data):
    """Handle invoice.payment_succeeded - set pro member status to true"""
    try:
        customer_id = invoice_data.get('customer')
        
        if not customer_id:
            logger.warning("Invoice missing customer ID")
            return
        
        # Find user by customer ID
        user_id = firestore_manager.get_user_by_customer_id(customer_id)
        if not user_id:
            logger.warning(f"No user found for customer ID: {customer_id}")
            return
        
        # Set user as pro member (payment succeeded)
        firestore_manager.set_pro_member_status(user_id, True)
        
        logger.info(f"Set pro member status to True for user {user_id} after successful payment")
        
    except Exception as e:
        logger.error(f"Error handling payment succeeded: {e}")
        raise


async def handle_payment_failed(invoice_data):
    """Handle invoice.payment_failed - set pro member status to false"""
    try:
        customer_id = invoice_data.get('customer')
        
        if not customer_id:
            logger.warning("Invoice missing customer ID")
            return
        
        # Find user by customer ID
        user_id = firestore_manager.get_user_by_customer_id(customer_id)
        if not user_id:
            logger.warning(f"No user found for customer ID: {customer_id}")
            return
        
        # Set user as non-pro member (payment failed)
        firestore_manager.set_pro_member_status(user_id, False)
        
        logger.info(f"Set pro member status to False for user {user_id} after payment failure")
        
    except Exception as e:
        logger.error(f"Error handling payment failed: {e}")
        raise


async def handle_subscription_updated(subscription_data):
    """Handle customer.subscription.updated - update pro member status based on subscription status"""
    try:
        customer_id = subscription_data.get('customer')
        subscription_id = subscription_data.get('id')
        status = subscription_data.get('status')
        
        if not customer_id or not subscription_id:
            logger.warning("Subscription update missing customer or subscription ID")
            return
        
        # Find user by customer ID
        user_id = firestore_manager.get_user_by_customer_id(customer_id)
        if not user_id:
            logger.warning(f"No user found for customer ID: {customer_id}")
            return
        
        # Set pro member status based on subscription status
        is_pro = status in ['active', 'trialing']
        firestore_manager.set_pro_member_status(user_id, is_pro)
        
        logger.info(f"Updated pro member status to {is_pro} for user {user_id} (subscription status: {status})")
        
    except Exception as e:
        logger.error(f"Error handling subscription updated: {e}")
        raise


async def handle_subscription_deleted(subscription_data):
    """Handle customer.subscription.deleted - set pro member status to false and clear subscription"""
    try:
        customer_id = subscription_data.get('customer')
        subscription_id = subscription_data.get('id')
        
        if not customer_id or not subscription_id:
            logger.warning("Subscription deletion missing customer or subscription ID")
            return
        
        # Find user by customer ID
        user_id = firestore_manager.get_user_by_customer_id(customer_id)
        if not user_id:
            logger.warning(f"No user found for customer ID: {customer_id}")
            return
        
        # Clear subscription ID and set pro member status to false
        firestore_manager.update_subscription_id(user_id, None)
        firestore_manager.set_pro_member_status(user_id, False)
        
        logger.info(f"Cleared subscription and set pro member status to False for user {user_id}")
        
    except Exception as e:
        logger.error(f"Error handling subscription deleted: {e}")
        raise
