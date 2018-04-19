# REST - API
* JSON
* Basic Authentication
## User

### /api/login/
Endpoint for testing login, returns if login was successfull.
### /api/user/register
* POST only

Body must contain (as JSON):
* password
* username

Optional:
* telegram_id

If the telegram_id is supplied, the register-telegram endpoint will be invoked after user creation.

Returns if user creation was successful, or a reason for failure.
### /api/user/register-telegram/[_telegram_id_]
Starts the registration process for a telegram_id for the currently logged in user.

Returns if sending of registration message was successful, or a reason for failure.
### /api/user/update/password/
* POST only

Body must contain (as JSON):
* password

Updates the password for the currently logged in user.
## Shop

### /api/shops
Returns all Shops, and supports Eve-SQLAlchemy queries.
### /api/products
Returns all Products, and supports Eve-SQLAlchemy queries.
### /api/order/[_prod_id_]/[_anz_]/[_comment_]
Order a product as the currently logged in user.
### /api/order/cancel/[_order_id_]/[_reason_]
Cancel an order as the currently logged in user.
### /api/order/approve/[_order_id_]
Approve an order as the currently logged in user.
### /api/order/finish/[_order_id_]
Finish an order as the currently logged in user.
### /api/order/deny/[_order_id_]/[_reason_]
Deny an order as the currently logged in user.
### /api/orders/unapproved/
Get all unapproved orders for your current user.
### /api/orders/open/
Get all open orders for your current user.


