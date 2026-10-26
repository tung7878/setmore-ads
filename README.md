# Meta Ads Studio — Streamlit + GitHub MVP

Default Setmore booking page: https://skinarin7clinic.setmore.com

## Run locally
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Deploy via GitHub + Streamlit Community Cloud
1. Create a GitHub repository and upload every file in this folder.
2. In Streamlit Community Cloud click Create app, select your repository, and use `streamlit_app.py` as the entrypoint.
3. In App settings → Secrets, configure:
```toml
SETMORE_BOOKING_URL = "https://skinarin7clinic.setmore.com"
META_APP_ID = "your_meta_app_id"
META_APP_SECRET = "your_meta_app_secret"
META_API_VERSION = "vXX.X"
META_REDIRECT_URI = "https://YOUR-APP-NAME.streamlit.app/"
```
Replace `vXX.X` with a Graph API version currently supported by Meta. Register the exact redirect URI in Meta Developer settings. Never commit secrets.

## Included
- Dashboard for Skinarin7 Clinic.
- Campaign draft builder with £5–£10/day selector, review step and simulated Instagram ad preview.
- Setmore URL builder with UTM parameters (`utm_source`, `utm_medium`, `utm_campaign`, `utm_content`).
- JSON/CSV draft export.
- Optional Meta OAuth flow and read-only ad-account/last-7-day Insights requests after valid configuration and permissions.
- Setmore Google Analytics setup guidance.

## Not yet implemented
- Actual campaign/ad creation or publishing (intentionally disabled).
- Persistent encrypted token/draft storage, multi-user authentication, audit database or background jobs.
- Verified appointment attribution per ad / automated Setmore appointment sync.

## Security
- The Meta token is held in Streamlit session state only; it is not persistently stored in an encrypted database. A new session may require reconnecting.
- Add authentication and durable server-side encrypted token storage before operating publicly.
- Never commit secrets, access tokens or passwords to GitHub. Use Streamlit Cloud Secrets.
- UTM tagging classifies traffic; it does not prove a booking was completed. Reconcile against Setmore/GA4.
- Code syntax was checked but the app has not been tested end-to-end with a live Meta developer app/account or deployed Streamlit instance.

## Official references
- Streamlit deploy: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
- Streamlit secrets: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management
- Setmore Booking Page URL: https://support.setmore.com/en/articles/490970-your-booking-page-url
- Setmore Google Analytics: https://support.setmore.com/en/articles/490934-connect-setmore-with-google-analytics
- Meta Marketing API: https://developers.facebook.com/docs/marketing-apis/
