# turvo_secrets.py
# DO NOT COMMIT THIS FILE

USE_SANDBOX = False

if USE_SANDBOX:
    CLIENT_ID = "publicapi"
    CLIENT_SECRET = "secret"
    API_KEY = "F2tfSseWLi4wEuKzHGEh71vFPBB7GQ8Pal62E9co"
    USERNAME = "Mukund@t3ralogistics.com"
    PASSWORD = "Mukund@12345678"
    CUSTOMER_ID = 850901
    CUSTOMER_NAME = "DIAMOND PET FOODS"
    BASE_URL = "https://my-sandbox-publicapi.turvo.com"
    APP_URL = "https://my-sandbox.turvo.com"
    APP_TURVO_TOKEN_URL = "https://my-sandbox.turvo.com/lobby/oauth/token"
    ACTIVITY_URL = "https://my-sandbox.turvo.com//api/activity/list"


else:
    CLIENT_ID = "publicapi"
    CLIENT_SECRET = "secret"
    API_KEY = "1ksCELBULY92puyweCLvX57S3tEvrJUM4dL9ZzUY"
    USERNAME = "Mukund@t3ralogistics.com"
    PASSWORD = "Mukundag1999@gmail"
    CUSTOMER_ID = 5850950
    CUSTOMER_NAME = "DIAMOND PET FOODS"
    BASE_URL = "https://publicapi.turvo.com"
    APP_URL = "https://app.turvo.com"
    APP_TURVO_TOKEN_URL = "https://app.turvo.com/lobby/oauth/token"
    ACTIVITY_URL = "https://app.turvo.com/api/activity/list"

# Webhook shared token you set in Turvo Webhook Profile (UI)
WEBHOOK_SHARED_TOKEN = "1234"

GS_CLIENT_ID = "t3ralogistics"
GS_CLIENT_SECRET = "7d01905c-d1b4-4675-96cc-c88b227e5bcb"
GS_BATCH_PREDICTION_URL = "https://app.greenscreens.ai/v3/prediction/batch-network-rates"
GS_AUTH_URL = "https://api.greenscreens.ai/v1/auth/token"
GS_PREDICTION_URL = "https://app.greenscreens.ai/v3/prediction/network-rates"

# DAT credentials + endpoints
# Toggle DAT environment:
# True  -> staging DAT APIs/credentials
# False -> production DAT APIs/credentials
USE_DAT_STAGING = False

if USE_DAT_STAGING:
    DAT_ORG_EMAIL = "leaders@t3ralogistics.com"
    DAT_ORG_PASSWORD = "DAT@api1357t3ralog"
    DAT_USER_EMAIL = "mac@t3ralogistics.com"
    DAT_USER_PASSWORD = "Dat@2151API12345"
    DAT_ORG_TOKEN_URL = "https://identity.api.staging.dat.com/access/v1/token/organization"
    DAT_USER_TOKEN_URL = "https://identity.api.staging.dat.com/access/v1/token/user"
    DAT_RATE_LOOKUP_URL = "https://analytics.api.staging.dat.com/linehaulrates/v1/lookups"
else:
    DAT_ORG_EMAIL = "mac@t3ralogistics.com"
    DAT_ORG_PASSWORD = "LeadersDAT@2025"
    DAT_USER_EMAIL = "leaders@t3ralogistics.com"
    DAT_USER_PASSWORD = "LeadersDATAPI@2025"
    DAT_ORG_TOKEN_URL = "https://identity.api.dat.com/access/v1/token/organization"
    DAT_USER_TOKEN_URL = "https://identity.api.dat.com/access/v1/token/user"
    DAT_RATE_LOOKUP_URL = "https://analytics.api.dat.com/linehaulrates/v1/lookups"


