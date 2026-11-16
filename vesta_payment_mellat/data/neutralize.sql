-- disable Bank Mellat payment provider
UPDATE payment_provider
   SET mellat_terminal_id = NULL,
       mellat_username = NULL,
       mellat_password = NULL;
