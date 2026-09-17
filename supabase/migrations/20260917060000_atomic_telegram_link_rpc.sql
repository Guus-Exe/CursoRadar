-- Migration: Atomic Telegram Account Linking RPC
-- Description: Executes token lookup, validation, atomic consumption, conflict resolution, and account linking in a single transaction.

CREATE OR REPLACE FUNCTION public.link_telegram_account(
    p_token text,
    p_telegram_chat_id text,
    p_telegram_username text DEFAULT NULL,
    p_telegram_first_name text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_token_record record;
    v_now timestamptz := clock_timestamp();
    v_account_id uuid;
    v_clean_token text := trim(p_token);
    v_clean_chat_id text := trim(p_telegram_chat_id);
BEGIN
    -- 1. Argument validation
    IF v_clean_token IS NULL OR v_clean_token = '' OR v_clean_chat_id IS NULL OR v_clean_chat_id = '' THEN
        RETURN jsonb_build_object(
            'success', false,
            'error_code', 'INVALID_ARGUMENTS',
            'message', '❌ Link de conexão inválido.'
        );
    END IF;

    -- 2. Lock token row to prevent concurrent double-spend / race conditions
    SELECT id, user_id, expires_at, used_at
    INTO v_token_record
    FROM public.telegram_link_tokens
    WHERE token = v_clean_token
    FOR UPDATE;

    -- 3. Validate existence
    IF NOT FOUND THEN
        RETURN jsonb_build_object(
            'success', false,
            'error_code', 'TOKEN_NOT_FOUND',
            'message', '❌ Link de conexão inválido.'
        );
    END IF;

    -- 4. Validate used_at
    IF v_token_record.used_at IS NOT NULL THEN
        RETURN jsonb_build_object(
            'success', false,
            'error_code', 'TOKEN_ALREADY_USED',
            'message', '⚠️ Este link já foi utilizado. Gere um novo link se precisar reconectar.'
        );
    END IF;

    -- 5. Validate expires_at
    IF v_now >= v_token_record.expires_at THEN
        RETURN jsonb_build_object(
            'success', false,
            'error_code', 'TOKEN_EXPIRED',
            'message', '⚠️ Este link expirou. Gere um novo link no CursoRadar.'
        );
    END IF;

    -- 6. Mark token as consumed in this transaction
    UPDATE public.telegram_link_tokens
    SET used_at = v_now
    WHERE id = v_token_record.id;

    -- 7. Resolve conflict on telegram_chat_id:
    -- Ensure telegram_chat_id is never linked to more than one user
    DELETE FROM public.telegram_accounts
    WHERE telegram_chat_id = v_clean_chat_id
      AND user_id != v_token_record.user_id;

    -- 8. Upsert into telegram_accounts for this user_id
    INSERT INTO public.telegram_accounts (
        user_id,
        telegram_chat_id,
        telegram_username,
        telegram_first_name,
        verified_at,
        active,
        created_at,
        updated_at
    )
    VALUES (
        v_token_record.user_id,
        v_clean_chat_id,
        p_telegram_username,
        p_telegram_first_name,
        v_now,
        true,
        v_now,
        v_now
    )
    ON CONFLICT (user_id) DO UPDATE SET
        telegram_chat_id = EXCLUDED.telegram_chat_id,
        telegram_username = EXCLUDED.telegram_username,
        telegram_first_name = EXCLUDED.telegram_first_name,
        verified_at = EXCLUDED.verified_at,
        active = true,
        updated_at = EXCLUDED.updated_at
    RETURNING id INTO v_account_id;

    -- 9. Return structured success result
    RETURN jsonb_build_object(
        'success', true,
        'message', '✅ Telegram conectado com sucesso ao CursoRadar.',
        'account_id', v_account_id,
        'user_id', v_token_record.user_id,
        'telegram_chat_id', v_clean_chat_id,
        'telegram_username', p_telegram_username,
        'telegram_first_name', p_telegram_first_name,
        'linked_at', v_now
    );
END;
$$;

-- Security: Revoke execute from PUBLIC, anon and authenticated
REVOKE ALL ON FUNCTION public.link_telegram_account(text, text, text, text) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.link_telegram_account(text, text, text, text) FROM anon;
REVOKE EXECUTE ON FUNCTION public.link_telegram_account(text, text, text, text) FROM authenticated;

-- Grant execute only to service_role
GRANT EXECUTE ON FUNCTION public.link_telegram_account(text, text, text, text) TO service_role;
