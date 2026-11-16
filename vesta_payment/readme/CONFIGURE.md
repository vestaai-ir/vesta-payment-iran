1. Set the system parameter `web.base.url` to the HTTPS address of the site and freeze it (`web.base.url.freeze = True`); the banks send customers back to this address.
2. Install a bank from **Vesta Gateway > Banks**, then click **Configure** and enter the credentials given by the bank (or by banktest.ir in test mode).
3. Click **Test Mode** and **Test Connection**, make a test purchase, then enter the production credentials and click **Go Live**.
4. Register the public IP address of the server with every bank.

See `docs/ACTIVATION.md` for the full guide, in Persian.
