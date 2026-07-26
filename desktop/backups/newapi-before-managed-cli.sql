--
-- PostgreSQL database dump
--

\restrict 47kr0bVCTTLMdY2fTaFw3BwOrE4HSFec0keCIthjDkKioZDwucRQJ8Nqd9hg5Sb

-- Dumped from database version 16.14
-- Dumped by pg_dump version 16.14

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: abilities; Type: TABLE; Schema: public; Owner: budgetloop
--

CREATE TABLE public.abilities (
    "group" character varying(64) NOT NULL,
    model character varying(255) NOT NULL,
    channel_id bigint NOT NULL,
    enabled boolean,
    priority bigint DEFAULT 0,
    weight bigint DEFAULT 0,
    tag text
);


ALTER TABLE public.abilities OWNER TO budgetloop;

--
-- Name: authz_roles; Type: TABLE; Schema: public; Owner: budgetloop
--

CREATE TABLE public.authz_roles (
    id bigint NOT NULL,
    key character varying(64) NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    built_in boolean,
    enabled boolean,
    sort bigint,
    created_at bigint,
    updated_at bigint
);


ALTER TABLE public.authz_roles OWNER TO budgetloop;

--
-- Name: authz_roles_id_seq; Type: SEQUENCE; Schema: public; Owner: budgetloop
--

CREATE SEQUENCE public.authz_roles_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.authz_roles_id_seq OWNER TO budgetloop;

--
-- Name: authz_roles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: budgetloop
--

ALTER SEQUENCE public.authz_roles_id_seq OWNED BY public.authz_roles.id;


--
-- Name: casbin_rule; Type: TABLE; Schema: public; Owner: budgetloop
--

CREATE TABLE public.casbin_rule (
    id bigint NOT NULL,
    ptype character varying(100),
    v0 character varying(100),
    v1 character varying(100),
    v2 character varying(100),
    v3 character varying(100),
    v4 character varying(100),
    v5 character varying(100)
);


ALTER TABLE public.casbin_rule OWNER TO budgetloop;

--
-- Name: casbin_rule_id_seq; Type: SEQUENCE; Schema: public; Owner: budgetloop
--

CREATE SEQUENCE public.casbin_rule_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.casbin_rule_id_seq OWNER TO budgetloop;

--
-- Name: casbin_rule_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: budgetloop
--

ALTER SEQUENCE public.casbin_rule_id_seq OWNED BY public.casbin_rule.id;


--
-- Name: channels; Type: TABLE; Schema: public; Owner: budgetloop
--

CREATE TABLE public.channels (
    id bigint NOT NULL,
    type bigint DEFAULT 0,
    key text NOT NULL,
    open_ai_organization text,
    test_model text,
    status bigint DEFAULT 1,
    name text,
    weight bigint DEFAULT 0,
    created_time bigint,
    test_time bigint,
    response_time bigint,
    base_url text DEFAULT ''::text,
    other text,
    balance numeric,
    balance_updated_time bigint,
    models text,
    "group" character varying(64) DEFAULT 'default'::character varying,
    used_quota bigint DEFAULT 0,
    model_mapping text,
    status_code_mapping character varying(1024) DEFAULT ''::character varying,
    priority bigint DEFAULT 0,
    auto_ban bigint DEFAULT 1,
    other_info text,
    tag text,
    setting text,
    param_override text,
    header_override text,
    remark character varying(255),
    channel_info json,
    settings text
);


ALTER TABLE public.channels OWNER TO budgetloop;

--
-- Name: channels_id_seq; Type: SEQUENCE; Schema: public; Owner: budgetloop
--

CREATE SEQUENCE public.channels_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.channels_id_seq OWNER TO budgetloop;

--
-- Name: channels_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: budgetloop
--

ALTER SEQUENCE public.channels_id_seq OWNED BY public.channels.id;


--
-- Name: checkins; Type: TABLE; Schema: public; Owner: budgetloop
--

CREATE TABLE public.checkins (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    checkin_date character varying(10) NOT NULL,
    quota_awarded bigint NOT NULL,
    created_at bigint
);


ALTER TABLE public.checkins OWNER TO budgetloop;

--
-- Name: checkins_id_seq; Type: SEQUENCE; Schema: public; Owner: budgetloop
--

CREATE SEQUENCE public.checkins_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.checkins_id_seq OWNER TO budgetloop;

--
-- Name: checkins_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: budgetloop
--

ALTER SEQUENCE public.checkins_id_seq OWNED BY public.checkins.id;


--
-- Name: custom_oauth_providers; Type: TABLE; Schema: public; Owner: budgetloop
--

CREATE TABLE public.custom_oauth_providers (
    id bigint NOT NULL,
    name character varying(64) NOT NULL,
    slug character varying(64) NOT NULL,
    icon character varying(128) DEFAULT ''::character varying,
    enabled boolean DEFAULT false,
    client_id character varying(256),
    client_secret character varying(512),
    authorization_endpoint character varying(512),
    token_endpoint character varying(512),
    user_info_endpoint character varying(512),
    scopes character varying(256) DEFAULT 'openid profile email'::character varying,
    user_id_field character varying(128) DEFAULT 'sub'::character varying,
    username_field character varying(128) DEFAULT 'preferred_username'::character varying,
    display_name_field character varying(128) DEFAULT 'name'::character varying,
    email_field character varying(128) DEFAULT 'email'::character varying,
    well_known character varying(512),
    auth_style bigint DEFAULT 0,
    access_policy text,
    access_denied_message character varying(512),
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);


ALTER TABLE public.custom_oauth_providers OWNER TO budgetloop;

--
-- Name: custom_oauth_providers_id_seq; Type: SEQUENCE; Schema: public; Owner: budgetloop
--

CREATE SEQUENCE public.custom_oauth_providers_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.custom_oauth_providers_id_seq OWNER TO budgetloop;

--
-- Name: custom_oauth_providers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: budgetloop
--

ALTER SEQUENCE public.custom_oauth_providers_id_seq OWNED BY public.custom_oauth_providers.id;


--
-- Name: logs; Type: TABLE; Schema: public; Owner: budgetloop
--

CREATE TABLE public.logs (
    id bigint NOT NULL,
    user_id bigint,
    created_at bigint,
    type bigint,
    content text,
    username text DEFAULT ''::text,
    token_name text DEFAULT ''::text,
    model_name text DEFAULT ''::text,
    quota bigint DEFAULT 0,
    prompt_tokens bigint DEFAULT 0,
    completion_tokens bigint DEFAULT 0,
    use_time bigint DEFAULT 0,
    is_stream boolean,
    channel_id bigint,
    channel_name text,
    token_id bigint DEFAULT 0,
    "group" text,
    ip text DEFAULT ''::text,
    request_id character varying(64) DEFAULT ''::character varying,
    upstream_request_id character varying(128) DEFAULT ''::character varying,
    other text
);


ALTER TABLE public.logs OWNER TO budgetloop;

--
-- Name: logs_id_seq; Type: SEQUENCE; Schema: public; Owner: budgetloop
--

CREATE SEQUENCE public.logs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.logs_id_seq OWNER TO budgetloop;

--
-- Name: logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: budgetloop
--

ALTER SEQUENCE public.logs_id_seq OWNED BY public.logs.id;


--
-- Name: midjourneys; Type: TABLE; Schema: public; Owner: budgetloop
--

CREATE TABLE public.midjourneys (
    id bigint NOT NULL,
    code bigint,
    user_id bigint,
    action character varying(40),
    mj_id text,
    prompt text,
    prompt_en text,
    description text,
    state text,
    submit_time bigint,
    start_time bigint,
    finish_time bigint,
    image_url text,
    video_url text,
    video_urls text,
    status character varying(20),
    progress character varying(30),
    fail_reason text,
    channel_id bigint,
    quota bigint,
    buttons text,
    properties text
);


ALTER TABLE public.midjourneys OWNER TO budgetloop;

--
-- Name: midjourneys_id_seq; Type: SEQUENCE; Schema: public; Owner: budgetloop
--

CREATE SEQUENCE public.midjourneys_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.midjourneys_id_seq OWNER TO budgetloop;

--
-- Name: midjourneys_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: budgetloop
--

ALTER SEQUENCE public.midjourneys_id_seq OWNED BY public.midjourneys.id;


--
-- Name: models; Type: TABLE; Schema: public; Owner: budgetloop
--

CREATE TABLE public.models (
    id bigint NOT NULL,
    model_name character varying(128) NOT NULL,
    description text,
    icon character varying(128),
    tags character varying(255),
    vendor_id bigint,
    endpoints text,
    status bigint DEFAULT 1,
    sync_official bigint DEFAULT 1,
    created_time bigint,
    updated_time bigint,
    deleted_at timestamp with time zone,
    name_rule bigint DEFAULT 0
);


ALTER TABLE public.models OWNER TO budgetloop;

--
-- Name: models_id_seq; Type: SEQUENCE; Schema: public; Owner: budgetloop
--

CREATE SEQUENCE public.models_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.models_id_seq OWNER TO budgetloop;

--
-- Name: models_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: budgetloop
--

ALTER SEQUENCE public.models_id_seq OWNED BY public.models.id;


--
-- Name: options; Type: TABLE; Schema: public; Owner: budgetloop
--

CREATE TABLE public.options (
    key text NOT NULL,
    value text
);


ALTER TABLE public.options OWNER TO budgetloop;

--
-- Name: passkey_credentials; Type: TABLE; Schema: public; Owner: budgetloop
--

CREATE TABLE public.passkey_credentials (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    credential_id character varying(512) NOT NULL,
    public_key text NOT NULL,
    attestation_type character varying(255),
    aa_guid character varying(512),
    sign_count bigint DEFAULT 0,
    clone_warning boolean,
    user_present boolean,
    user_verified boolean,
    backup_eligible boolean,
    backup_state boolean,
    transports text,
    attachment character varying(32),
    last_used_at timestamp with time zone,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    deleted_at timestamp with time zone
);


ALTER TABLE public.passkey_credentials OWNER TO budgetloop;

--
-- Name: passkey_credentials_id_seq; Type: SEQUENCE; Schema: public; Owner: budgetloop
--

CREATE SEQUENCE public.passkey_credentials_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.passkey_credentials_id_seq OWNER TO budgetloop;

--
-- Name: passkey_credentials_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: budgetloop
--

ALTER SEQUENCE public.passkey_credentials_id_seq OWNED BY public.passkey_credentials.id;


--
-- Name: perf_metrics; Type: TABLE; Schema: public; Owner: budgetloop
--

CREATE TABLE public.perf_metrics (
    id bigint NOT NULL,
    model_name character varying(128),
    "group" character varying(64),
    bucket_ts bigint,
    request_count bigint DEFAULT 0,
    success_count bigint DEFAULT 0,
    total_latency_ms bigint DEFAULT 0,
    ttft_sum_ms bigint DEFAULT 0,
    ttft_count bigint DEFAULT 0,
    output_tokens bigint DEFAULT 0,
    generation_ms bigint DEFAULT 0
);


ALTER TABLE public.perf_metrics OWNER TO budgetloop;

--
-- Name: perf_metrics_id_seq; Type: SEQUENCE; Schema: public; Owner: budgetloop
--

CREATE SEQUENCE public.perf_metrics_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.perf_metrics_id_seq OWNER TO budgetloop;

--
-- Name: perf_metrics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: budgetloop
--

ALTER SEQUENCE public.perf_metrics_id_seq OWNED BY public.perf_metrics.id;


--
-- Name: prefill_groups; Type: TABLE; Schema: public; Owner: budgetloop
--

CREATE TABLE public.prefill_groups (
    id bigint NOT NULL,
    name character varying(64) NOT NULL,
    type character varying(32) NOT NULL,
    items json,
    description character varying(255),
    created_time bigint,
    updated_time bigint,
    deleted_at timestamp with time zone
);


ALTER TABLE public.prefill_groups OWNER TO budgetloop;

--
-- Name: prefill_groups_id_seq; Type: SEQUENCE; Schema: public; Owner: budgetloop
--

CREATE SEQUENCE public.prefill_groups_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.prefill_groups_id_seq OWNER TO budgetloop;

--
-- Name: prefill_groups_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: budgetloop
--

ALTER SEQUENCE public.prefill_groups_id_seq OWNED BY public.prefill_groups.id;


--
-- Name: quota_data; Type: TABLE; Schema: public; Owner: budgetloop
--

CREATE TABLE public.quota_data (
    id bigint NOT NULL,
    user_id bigint,
    username character varying(64) DEFAULT ''::character varying,
    model_name character varying(64) DEFAULT ''::character varying,
    created_at bigint,
    use_group character varying(64) DEFAULT ''::character varying,
    token_id bigint DEFAULT 0,
    channel_id bigint DEFAULT 0,
    node_name character varying(64) DEFAULT ''::character varying,
    token_used bigint DEFAULT 0,
    count bigint DEFAULT 0,
    quota bigint DEFAULT 0
);


ALTER TABLE public.quota_data OWNER TO budgetloop;

--
-- Name: quota_data_id_seq; Type: SEQUENCE; Schema: public; Owner: budgetloop
--

CREATE SEQUENCE public.quota_data_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.quota_data_id_seq OWNER TO budgetloop;

--
-- Name: quota_data_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: budgetloop
--

ALTER SEQUENCE public.quota_data_id_seq OWNED BY public.quota_data.id;


--
-- Name: redemptions; Type: TABLE; Schema: public; Owner: budgetloop
--

CREATE TABLE public.redemptions (
    id bigint NOT NULL,
    user_id bigint,
    key character(32),
    status bigint DEFAULT 1,
    name text,
    quota bigint DEFAULT 100,
    created_time bigint,
    redeemed_time bigint,
    used_user_id bigint,
    deleted_at timestamp with time zone,
    expired_time bigint
);


ALTER TABLE public.redemptions OWNER TO budgetloop;

--
-- Name: redemptions_id_seq; Type: SEQUENCE; Schema: public; Owner: budgetloop
--

CREATE SEQUENCE public.redemptions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.redemptions_id_seq OWNER TO budgetloop;

--
-- Name: redemptions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: budgetloop
--

ALTER SEQUENCE public.redemptions_id_seq OWNED BY public.redemptions.id;


--
-- Name: setups; Type: TABLE; Schema: public; Owner: budgetloop
--

CREATE TABLE public.setups (
    id bigint NOT NULL,
    version character varying(50) NOT NULL,
    initialized_at bigint NOT NULL
);


ALTER TABLE public.setups OWNER TO budgetloop;

--
-- Name: setups_id_seq; Type: SEQUENCE; Schema: public; Owner: budgetloop
--

CREATE SEQUENCE public.setups_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.setups_id_seq OWNER TO budgetloop;

--
-- Name: setups_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: budgetloop
--

ALTER SEQUENCE public.setups_id_seq OWNED BY public.setups.id;


--
-- Name: subscription_orders; Type: TABLE; Schema: public; Owner: budgetloop
--

CREATE TABLE public.subscription_orders (
    id bigint NOT NULL,
    user_id bigint,
    plan_id bigint,
    money numeric,
    trade_no character varying(255),
    payment_method character varying(50),
    payment_provider character varying(50) DEFAULT ''::character varying,
    status text,
    create_time bigint,
    complete_time bigint,
    provider_payload text
);


ALTER TABLE public.subscription_orders OWNER TO budgetloop;

--
-- Name: subscription_orders_id_seq; Type: SEQUENCE; Schema: public; Owner: budgetloop
--

CREATE SEQUENCE public.subscription_orders_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.subscription_orders_id_seq OWNER TO budgetloop;

--
-- Name: subscription_orders_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: budgetloop
--

ALTER SEQUENCE public.subscription_orders_id_seq OWNED BY public.subscription_orders.id;


--
-- Name: subscription_plans; Type: TABLE; Schema: public; Owner: budgetloop
--

CREATE TABLE public.subscription_plans (
    id bigint NOT NULL,
    title character varying(128) NOT NULL,
    subtitle character varying(255) DEFAULT ''::character varying,
    price_amount numeric(10,6) DEFAULT 0.000000 NOT NULL,
    currency character varying(8) DEFAULT 'USD'::character varying NOT NULL,
    duration_unit character varying(16) DEFAULT 'month'::character varying NOT NULL,
    duration_value bigint DEFAULT 1 NOT NULL,
    custom_seconds bigint DEFAULT 0 NOT NULL,
    enabled boolean DEFAULT true,
    sort_order bigint DEFAULT 0,
    allow_balance_pay boolean,
    allow_wallet_overflow boolean,
    stripe_price_id character varying(128) DEFAULT ''::character varying,
    creem_product_id character varying(128) DEFAULT ''::character varying,
    waffo_pancake_product_id character varying(128) DEFAULT ''::character varying,
    max_purchase_per_user bigint DEFAULT 0,
    upgrade_group character varying(64) DEFAULT ''::character varying,
    downgrade_group character varying(64) DEFAULT ''::character varying,
    total_amount bigint DEFAULT 0 NOT NULL,
    quota_reset_period character varying(16) DEFAULT 'never'::character varying,
    quota_reset_custom_seconds bigint DEFAULT 0,
    created_at bigint,
    updated_at bigint
);


ALTER TABLE public.subscription_plans OWNER TO budgetloop;

--
-- Name: subscription_plans_id_seq; Type: SEQUENCE; Schema: public; Owner: budgetloop
--

CREATE SEQUENCE public.subscription_plans_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.subscription_plans_id_seq OWNER TO budgetloop;

--
-- Name: subscription_plans_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: budgetloop
--

ALTER SEQUENCE public.subscription_plans_id_seq OWNED BY public.subscription_plans.id;


--
-- Name: subscription_pre_consume_records; Type: TABLE; Schema: public; Owner: budgetloop
--

CREATE TABLE public.subscription_pre_consume_records (
    id bigint NOT NULL,
    request_id character varying(64),
    user_id bigint,
    user_subscription_id bigint,
    pre_consumed bigint DEFAULT 0 NOT NULL,
    status character varying(32),
    created_at bigint,
    updated_at bigint
);


ALTER TABLE public.subscription_pre_consume_records OWNER TO budgetloop;

--
-- Name: subscription_pre_consume_records_id_seq; Type: SEQUENCE; Schema: public; Owner: budgetloop
--

CREATE SEQUENCE public.subscription_pre_consume_records_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.subscription_pre_consume_records_id_seq OWNER TO budgetloop;

--
-- Name: subscription_pre_consume_records_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: budgetloop
--

ALTER SEQUENCE public.subscription_pre_consume_records_id_seq OWNED BY public.subscription_pre_consume_records.id;


--
-- Name: system_instances; Type: TABLE; Schema: public; Owner: budgetloop
--

CREATE TABLE public.system_instances (
    node_name character varying(128) NOT NULL,
    info text,
    started_at bigint,
    last_seen_at bigint,
    created_at bigint,
    updated_at bigint
);


ALTER TABLE public.system_instances OWNER TO budgetloop;

--
-- Name: system_task_locks; Type: TABLE; Schema: public; Owner: budgetloop
--

CREATE TABLE public.system_task_locks (
    type character varying(64) NOT NULL,
    task_id character varying(64),
    locked_by character varying(128),
    locked_until bigint,
    updated_at bigint
);


ALTER TABLE public.system_task_locks OWNER TO budgetloop;

--
-- Name: system_tasks; Type: TABLE; Schema: public; Owner: budgetloop
--

CREATE TABLE public.system_tasks (
    id bigint NOT NULL,
    task_id character varying(64),
    type character varying(64),
    status character varying(32),
    active_key character varying(64),
    payload text,
    state text,
    result text,
    error text,
    locked_by character varying(128),
    created_at bigint,
    updated_at bigint
);


ALTER TABLE public.system_tasks OWNER TO budgetloop;

--
-- Name: system_tasks_id_seq; Type: SEQUENCE; Schema: public; Owner: budgetloop
--

CREATE SEQUENCE public.system_tasks_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.system_tasks_id_seq OWNER TO budgetloop;

--
-- Name: system_tasks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: budgetloop
--

ALTER SEQUENCE public.system_tasks_id_seq OWNED BY public.system_tasks.id;


--
-- Name: tasks; Type: TABLE; Schema: public; Owner: budgetloop
--

CREATE TABLE public.tasks (
    id bigint NOT NULL,
    created_at bigint,
    updated_at bigint,
    task_id character varying(191),
    platform character varying(30),
    user_id bigint,
    "group" character varying(50),
    channel_id bigint,
    quota bigint,
    action character varying(40),
    status character varying(20),
    fail_reason text,
    submit_time bigint,
    start_time bigint,
    finish_time bigint,
    progress character varying(20),
    properties json,
    private_data json,
    data json
);


ALTER TABLE public.tasks OWNER TO budgetloop;

--
-- Name: tasks_id_seq; Type: SEQUENCE; Schema: public; Owner: budgetloop
--

CREATE SEQUENCE public.tasks_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.tasks_id_seq OWNER TO budgetloop;

--
-- Name: tasks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: budgetloop
--

ALTER SEQUENCE public.tasks_id_seq OWNED BY public.tasks.id;


--
-- Name: tokens; Type: TABLE; Schema: public; Owner: budgetloop
--

CREATE TABLE public.tokens (
    id bigint NOT NULL,
    user_id bigint,
    key character varying(128),
    status bigint DEFAULT 1,
    name text,
    created_time bigint,
    accessed_time bigint,
    expired_time bigint DEFAULT '-1'::integer,
    remain_quota bigint DEFAULT 0,
    unlimited_quota boolean,
    model_limits_enabled boolean,
    model_limits text,
    allow_ips text DEFAULT ''::text,
    used_quota bigint DEFAULT 0,
    "group" text DEFAULT ''::text,
    cross_group_retry boolean,
    deleted_at timestamp with time zone
);


ALTER TABLE public.tokens OWNER TO budgetloop;

--
-- Name: tokens_id_seq; Type: SEQUENCE; Schema: public; Owner: budgetloop
--

CREATE SEQUENCE public.tokens_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.tokens_id_seq OWNER TO budgetloop;

--
-- Name: tokens_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: budgetloop
--

ALTER SEQUENCE public.tokens_id_seq OWNED BY public.tokens.id;


--
-- Name: top_ups; Type: TABLE; Schema: public; Owner: budgetloop
--

CREATE TABLE public.top_ups (
    id bigint NOT NULL,
    user_id bigint,
    amount bigint,
    money numeric,
    trade_no character varying(255),
    payment_method character varying(50),
    payment_provider character varying(50) DEFAULT ''::character varying,
    create_time bigint,
    complete_time bigint,
    status text
);


ALTER TABLE public.top_ups OWNER TO budgetloop;

--
-- Name: top_ups_id_seq; Type: SEQUENCE; Schema: public; Owner: budgetloop
--

CREATE SEQUENCE public.top_ups_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.top_ups_id_seq OWNER TO budgetloop;

--
-- Name: top_ups_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: budgetloop
--

ALTER SEQUENCE public.top_ups_id_seq OWNED BY public.top_ups.id;


--
-- Name: two_fa_backup_codes; Type: TABLE; Schema: public; Owner: budgetloop
--

CREATE TABLE public.two_fa_backup_codes (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    code_hash character varying(255) NOT NULL,
    is_used boolean,
    used_at timestamp with time zone,
    created_at timestamp with time zone,
    deleted_at timestamp with time zone
);


ALTER TABLE public.two_fa_backup_codes OWNER TO budgetloop;

--
-- Name: two_fa_backup_codes_id_seq; Type: SEQUENCE; Schema: public; Owner: budgetloop
--

CREATE SEQUENCE public.two_fa_backup_codes_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.two_fa_backup_codes_id_seq OWNER TO budgetloop;

--
-- Name: two_fa_backup_codes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: budgetloop
--

ALTER SEQUENCE public.two_fa_backup_codes_id_seq OWNED BY public.two_fa_backup_codes.id;


--
-- Name: two_fas; Type: TABLE; Schema: public; Owner: budgetloop
--

CREATE TABLE public.two_fas (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    secret character varying(255) NOT NULL,
    is_enabled boolean,
    failed_attempts bigint DEFAULT 0,
    locked_until timestamp with time zone,
    last_used_at timestamp with time zone,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    deleted_at timestamp with time zone
);


ALTER TABLE public.two_fas OWNER TO budgetloop;

--
-- Name: two_fas_id_seq; Type: SEQUENCE; Schema: public; Owner: budgetloop
--

CREATE SEQUENCE public.two_fas_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.two_fas_id_seq OWNER TO budgetloop;

--
-- Name: two_fas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: budgetloop
--

ALTER SEQUENCE public.two_fas_id_seq OWNED BY public.two_fas.id;


--
-- Name: user_oauth_bindings; Type: TABLE; Schema: public; Owner: budgetloop
--

CREATE TABLE public.user_oauth_bindings (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    provider_id bigint NOT NULL,
    provider_user_id character varying(256) NOT NULL,
    created_at timestamp with time zone
);


ALTER TABLE public.user_oauth_bindings OWNER TO budgetloop;

--
-- Name: user_oauth_bindings_id_seq; Type: SEQUENCE; Schema: public; Owner: budgetloop
--

CREATE SEQUENCE public.user_oauth_bindings_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_oauth_bindings_id_seq OWNER TO budgetloop;

--
-- Name: user_oauth_bindings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: budgetloop
--

ALTER SEQUENCE public.user_oauth_bindings_id_seq OWNED BY public.user_oauth_bindings.id;


--
-- Name: user_subscriptions; Type: TABLE; Schema: public; Owner: budgetloop
--

CREATE TABLE public.user_subscriptions (
    id bigint NOT NULL,
    user_id bigint,
    plan_id bigint,
    amount_total bigint DEFAULT 0 NOT NULL,
    amount_used bigint DEFAULT 0 NOT NULL,
    start_time bigint,
    end_time bigint,
    status character varying(32),
    source character varying(32) DEFAULT 'order'::character varying,
    last_reset_time bigint DEFAULT 0,
    next_reset_time bigint DEFAULT 0,
    upgrade_group character varying(64) DEFAULT ''::character varying,
    prev_user_group character varying(64) DEFAULT ''::character varying,
    downgrade_group character varying(64) DEFAULT ''::character varying,
    allow_wallet_overflow boolean,
    created_at bigint,
    updated_at bigint
);


ALTER TABLE public.user_subscriptions OWNER TO budgetloop;

--
-- Name: user_subscriptions_id_seq; Type: SEQUENCE; Schema: public; Owner: budgetloop
--

CREATE SEQUENCE public.user_subscriptions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_subscriptions_id_seq OWNER TO budgetloop;

--
-- Name: user_subscriptions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: budgetloop
--

ALTER SEQUENCE public.user_subscriptions_id_seq OWNED BY public.user_subscriptions.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: budgetloop
--

CREATE TABLE public.users (
    id bigint NOT NULL,
    username text,
    password text NOT NULL,
    display_name text,
    role bigint DEFAULT 1,
    status bigint DEFAULT 1,
    email text,
    github_id text,
    discord_id text,
    oidc_id text,
    wechat_id text,
    telegram_id text,
    access_token character(32),
    quota bigint DEFAULT 0,
    used_quota bigint DEFAULT 0,
    request_count bigint DEFAULT 0,
    "group" character varying(64) DEFAULT 'default'::character varying,
    aff_code character varying(32),
    aff_count bigint DEFAULT 0,
    aff_quota bigint DEFAULT 0,
    aff_history bigint DEFAULT 0,
    inviter_id bigint,
    deleted_at timestamp with time zone,
    linux_do_id text,
    setting text,
    remark character varying(255),
    stripe_customer character varying(64),
    created_at bigint,
    last_login_at bigint DEFAULT 0
);


ALTER TABLE public.users OWNER TO budgetloop;

--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: budgetloop
--

CREATE SEQUENCE public.users_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.users_id_seq OWNER TO budgetloop;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: budgetloop
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: vendors; Type: TABLE; Schema: public; Owner: budgetloop
--

CREATE TABLE public.vendors (
    id bigint NOT NULL,
    name character varying(128) NOT NULL,
    description text,
    icon character varying(128),
    status bigint DEFAULT 1,
    created_time bigint,
    updated_time bigint,
    deleted_at timestamp with time zone
);


ALTER TABLE public.vendors OWNER TO budgetloop;

--
-- Name: vendors_id_seq; Type: SEQUENCE; Schema: public; Owner: budgetloop
--

CREATE SEQUENCE public.vendors_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.vendors_id_seq OWNER TO budgetloop;

--
-- Name: vendors_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: budgetloop
--

ALTER SEQUENCE public.vendors_id_seq OWNED BY public.vendors.id;


--
-- Name: authz_roles id; Type: DEFAULT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.authz_roles ALTER COLUMN id SET DEFAULT nextval('public.authz_roles_id_seq'::regclass);


--
-- Name: casbin_rule id; Type: DEFAULT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.casbin_rule ALTER COLUMN id SET DEFAULT nextval('public.casbin_rule_id_seq'::regclass);


--
-- Name: channels id; Type: DEFAULT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.channels ALTER COLUMN id SET DEFAULT nextval('public.channels_id_seq'::regclass);


--
-- Name: checkins id; Type: DEFAULT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.checkins ALTER COLUMN id SET DEFAULT nextval('public.checkins_id_seq'::regclass);


--
-- Name: custom_oauth_providers id; Type: DEFAULT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.custom_oauth_providers ALTER COLUMN id SET DEFAULT nextval('public.custom_oauth_providers_id_seq'::regclass);


--
-- Name: logs id; Type: DEFAULT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.logs ALTER COLUMN id SET DEFAULT nextval('public.logs_id_seq'::regclass);


--
-- Name: midjourneys id; Type: DEFAULT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.midjourneys ALTER COLUMN id SET DEFAULT nextval('public.midjourneys_id_seq'::regclass);


--
-- Name: models id; Type: DEFAULT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.models ALTER COLUMN id SET DEFAULT nextval('public.models_id_seq'::regclass);


--
-- Name: passkey_credentials id; Type: DEFAULT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.passkey_credentials ALTER COLUMN id SET DEFAULT nextval('public.passkey_credentials_id_seq'::regclass);


--
-- Name: perf_metrics id; Type: DEFAULT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.perf_metrics ALTER COLUMN id SET DEFAULT nextval('public.perf_metrics_id_seq'::regclass);


--
-- Name: prefill_groups id; Type: DEFAULT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.prefill_groups ALTER COLUMN id SET DEFAULT nextval('public.prefill_groups_id_seq'::regclass);


--
-- Name: quota_data id; Type: DEFAULT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.quota_data ALTER COLUMN id SET DEFAULT nextval('public.quota_data_id_seq'::regclass);


--
-- Name: redemptions id; Type: DEFAULT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.redemptions ALTER COLUMN id SET DEFAULT nextval('public.redemptions_id_seq'::regclass);


--
-- Name: setups id; Type: DEFAULT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.setups ALTER COLUMN id SET DEFAULT nextval('public.setups_id_seq'::regclass);


--
-- Name: subscription_orders id; Type: DEFAULT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.subscription_orders ALTER COLUMN id SET DEFAULT nextval('public.subscription_orders_id_seq'::regclass);


--
-- Name: subscription_plans id; Type: DEFAULT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.subscription_plans ALTER COLUMN id SET DEFAULT nextval('public.subscription_plans_id_seq'::regclass);


--
-- Name: subscription_pre_consume_records id; Type: DEFAULT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.subscription_pre_consume_records ALTER COLUMN id SET DEFAULT nextval('public.subscription_pre_consume_records_id_seq'::regclass);


--
-- Name: system_tasks id; Type: DEFAULT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.system_tasks ALTER COLUMN id SET DEFAULT nextval('public.system_tasks_id_seq'::regclass);


--
-- Name: tasks id; Type: DEFAULT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.tasks ALTER COLUMN id SET DEFAULT nextval('public.tasks_id_seq'::regclass);


--
-- Name: tokens id; Type: DEFAULT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.tokens ALTER COLUMN id SET DEFAULT nextval('public.tokens_id_seq'::regclass);


--
-- Name: top_ups id; Type: DEFAULT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.top_ups ALTER COLUMN id SET DEFAULT nextval('public.top_ups_id_seq'::regclass);


--
-- Name: two_fa_backup_codes id; Type: DEFAULT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.two_fa_backup_codes ALTER COLUMN id SET DEFAULT nextval('public.two_fa_backup_codes_id_seq'::regclass);


--
-- Name: two_fas id; Type: DEFAULT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.two_fas ALTER COLUMN id SET DEFAULT nextval('public.two_fas_id_seq'::regclass);


--
-- Name: user_oauth_bindings id; Type: DEFAULT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.user_oauth_bindings ALTER COLUMN id SET DEFAULT nextval('public.user_oauth_bindings_id_seq'::regclass);


--
-- Name: user_subscriptions id; Type: DEFAULT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.user_subscriptions ALTER COLUMN id SET DEFAULT nextval('public.user_subscriptions_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: vendors id; Type: DEFAULT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.vendors ALTER COLUMN id SET DEFAULT nextval('public.vendors_id_seq'::regclass);


--
-- Data for Name: abilities; Type: TABLE DATA; Schema: public; Owner: budgetloop
--

COPY public.abilities ("group", model, channel_id, enabled, priority, weight, tag) FROM stdin;
\.


--
-- Data for Name: authz_roles; Type: TABLE DATA; Schema: public; Owner: budgetloop
--

COPY public.authz_roles (id, key, name, description, built_in, enabled, sort, created_at, updated_at) FROM stdin;
1	root	Root	Built-in root authorization role	t	t	0	1784990218	1784990218
2	admin	Admin	Built-in admin authorization role	t	t	10	1784990218	1784990218
\.


--
-- Data for Name: casbin_rule; Type: TABLE DATA; Schema: public; Owner: budgetloop
--

COPY public.casbin_rule (id, ptype, v0, v1, v2, v3, v4, v5) FROM stdin;
10	p	role:admin	channel	read	allow		
11	p	role:admin	channel	operate	allow		
12	p	role:admin	channel	write	allow		
\.


--
-- Data for Name: channels; Type: TABLE DATA; Schema: public; Owner: budgetloop
--

COPY public.channels (id, type, key, open_ai_organization, test_model, status, name, weight, created_time, test_time, response_time, base_url, other, balance, balance_updated_time, models, "group", used_quota, model_mapping, status_code_mapping, priority, auto_ban, other_info, tag, setting, param_override, header_override, remark, channel_info, settings) FROM stdin;
\.


--
-- Data for Name: checkins; Type: TABLE DATA; Schema: public; Owner: budgetloop
--

COPY public.checkins (id, user_id, checkin_date, quota_awarded, created_at) FROM stdin;
\.


--
-- Data for Name: custom_oauth_providers; Type: TABLE DATA; Schema: public; Owner: budgetloop
--

COPY public.custom_oauth_providers (id, name, slug, icon, enabled, client_id, client_secret, authorization_endpoint, token_endpoint, user_info_endpoint, scopes, user_id_field, username_field, display_name_field, email_field, well_known, auth_style, access_policy, access_denied_message, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: logs; Type: TABLE DATA; Schema: public; Owner: budgetloop
--

COPY public.logs (id, user_id, created_at, type, content, username, token_name, model_name, quota, prompt_tokens, completion_tokens, use_time, is_stream, channel_id, channel_name, token_id, "group", ip, request_id, upstream_request_id, other) FROM stdin;
\.


--
-- Data for Name: midjourneys; Type: TABLE DATA; Schema: public; Owner: budgetloop
--

COPY public.midjourneys (id, code, user_id, action, mj_id, prompt, prompt_en, description, state, submit_time, start_time, finish_time, image_url, video_url, video_urls, status, progress, fail_reason, channel_id, quota, buttons, properties) FROM stdin;
\.


--
-- Data for Name: models; Type: TABLE DATA; Schema: public; Owner: budgetloop
--

COPY public.models (id, model_name, description, icon, tags, vendor_id, endpoints, status, sync_official, created_time, updated_time, deleted_at, name_rule) FROM stdin;
\.


--
-- Data for Name: options; Type: TABLE DATA; Schema: public; Owner: budgetloop
--

COPY public.options (key, value) FROM stdin;
\.


--
-- Data for Name: passkey_credentials; Type: TABLE DATA; Schema: public; Owner: budgetloop
--

COPY public.passkey_credentials (id, user_id, credential_id, public_key, attestation_type, aa_guid, sign_count, clone_warning, user_present, user_verified, backup_eligible, backup_state, transports, attachment, last_used_at, created_at, updated_at, deleted_at) FROM stdin;
\.


--
-- Data for Name: perf_metrics; Type: TABLE DATA; Schema: public; Owner: budgetloop
--

COPY public.perf_metrics (id, model_name, "group", bucket_ts, request_count, success_count, total_latency_ms, ttft_sum_ms, ttft_count, output_tokens, generation_ms) FROM stdin;
\.


--
-- Data for Name: prefill_groups; Type: TABLE DATA; Schema: public; Owner: budgetloop
--

COPY public.prefill_groups (id, name, type, items, description, created_time, updated_time, deleted_at) FROM stdin;
\.


--
-- Data for Name: quota_data; Type: TABLE DATA; Schema: public; Owner: budgetloop
--

COPY public.quota_data (id, user_id, username, model_name, created_at, use_group, token_id, channel_id, node_name, token_used, count, quota) FROM stdin;
\.


--
-- Data for Name: redemptions; Type: TABLE DATA; Schema: public; Owner: budgetloop
--

COPY public.redemptions (id, user_id, key, status, name, quota, created_time, redeemed_time, used_user_id, deleted_at, expired_time) FROM stdin;
\.


--
-- Data for Name: setups; Type: TABLE DATA; Schema: public; Owner: budgetloop
--

COPY public.setups (id, version, initialized_at) FROM stdin;
\.


--
-- Data for Name: subscription_orders; Type: TABLE DATA; Schema: public; Owner: budgetloop
--

COPY public.subscription_orders (id, user_id, plan_id, money, trade_no, payment_method, payment_provider, status, create_time, complete_time, provider_payload) FROM stdin;
\.


--
-- Data for Name: subscription_plans; Type: TABLE DATA; Schema: public; Owner: budgetloop
--

COPY public.subscription_plans (id, title, subtitle, price_amount, currency, duration_unit, duration_value, custom_seconds, enabled, sort_order, allow_balance_pay, allow_wallet_overflow, stripe_price_id, creem_product_id, waffo_pancake_product_id, max_purchase_per_user, upgrade_group, downgrade_group, total_amount, quota_reset_period, quota_reset_custom_seconds, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: subscription_pre_consume_records; Type: TABLE DATA; Schema: public; Owner: budgetloop
--

COPY public.subscription_pre_consume_records (id, request_id, user_id, user_subscription_id, pre_consumed, status, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: system_instances; Type: TABLE DATA; Schema: public; Owner: budgetloop
--

COPY public.system_instances (node_name, info, started_at, last_seen_at, created_at, updated_at) FROM stdin;
budgetloop-new-api	{"schema_version":1,"node":{"name":"budgetloop-new-api","source":"manual","manually_configured":true,"should_configure_manually":false},"role":{"is_master":true},"runtime":{"version":"v1.0.0-rc.21","goos":"linux","goarch":"arm64","started_at":1785030659},"host":{"hostname":"a6d4a7273be0"},"resources":{"cpu":{"usage_percent":0.8211496094540152},"memory":{"usage_percent":24.39225839477855},"storage":{"total_bytes":485421555712,"used_bytes":47226200064,"free_bytes":413462020096,"used_percent":9.728904600194403}}}	1785030659	1785056431	1784990218	1785056431
\.


--
-- Data for Name: system_task_locks; Type: TABLE DATA; Schema: public; Owner: budgetloop
--

COPY public.system_task_locks (type, task_id, locked_by, locked_until, updated_at) FROM stdin;
\.


--
-- Data for Name: system_tasks; Type: TABLE DATA; Schema: public; Owner: budgetloop
--

COPY public.system_tasks (id, task_id, type, status, active_key, payload, state, result, error, locked_by, created_at, updated_at) FROM stdin;
1	systask_uBrZ9wPHg8mLgmNWK6aZeKBaPJA0I1hb	model_update	succeeded	\N		{"total":0,"processed":0,"progress":100}	{"checked_channels":0,"changed_channels":0,"detected_add_models":0,"detected_remove_models":0,"failed_channels":0,"auto_added_models":0}		budgetloop-new-api-LJH76o0j	1784990218	1784990218
2	systask_DUO8SGWkh3GoElwluV3UDMV6k2WG6ikk	model_update	succeeded	\N		{"total":0,"processed":0,"progress":100}	{"checked_channels":0,"changed_channels":0,"detected_add_models":0,"detected_remove_models":0,"failed_channels":0,"auto_added_models":0}		budgetloop-new-api-LJH76o0j	1784992018	1784992018
3	systask_MbQXt9pelKRUjWMkPgmddpm6cva6mN5A	model_update	succeeded	\N		{"total":0,"processed":0,"progress":100}	{"checked_channels":0,"changed_channels":0,"detected_add_models":0,"detected_remove_models":0,"failed_channels":0,"auto_added_models":0}		budgetloop-new-api-LJH76o0j	1784993833	1784993833
10	systask_EISiAxaXsQjqWTg4JkHIRk6ecrcWrc3r	model_update	succeeded	\N		{"total":0,"processed":0,"progress":100}	{"checked_channels":0,"changed_channels":0,"detected_add_models":0,"detected_remove_models":0,"failed_channels":0,"auto_added_models":0}		budgetloop-new-api-Ll4ilylC	1785036901	1785036901
4	systask_S0ulGcejA2kA2eWYMHy4tF8wlejEuQ9p	model_update	succeeded	\N		{"total":0,"processed":0,"progress":100}	{"checked_channels":0,"changed_channels":0,"detected_add_models":0,"detected_remove_models":0,"failed_channels":0,"auto_added_models":0}		budgetloop-new-api-LJH76o0j	1784995633	1784995633
5	systask_mvQ85Orcalk885Bvi9sg9u8hPmuVD4hj	model_update	succeeded	\N		{"total":0,"processed":0,"progress":100}	{"checked_channels":0,"changed_channels":0,"detected_add_models":0,"detected_remove_models":0,"failed_channels":0,"auto_added_models":0}		budgetloop-new-api-XpeqvOyL	1785027883	1785027883
6	systask_ogzfyLXabxh9wDB6Z13sURThXxJJ50x8	model_update	succeeded	\N		{"total":0,"processed":0,"progress":100}	{"checked_channels":0,"changed_channels":0,"detected_add_models":0,"detected_remove_models":0,"failed_channels":0,"auto_added_models":0}		budgetloop-new-api-KxbXXM6t	1785029683	1785029683
7	systask_h0j3FwTFda4I1pHKZsOEHNvT8DgXzF6j	model_update	succeeded	\N		{"total":0,"processed":0,"progress":100}	{"checked_channels":0,"changed_channels":0,"detected_add_models":0,"detected_remove_models":0,"failed_channels":0,"auto_added_models":0}		budgetloop-new-api-Ll4ilylC	1785031486	1785031486
11	systask_QpvHKsJzdLLobxE56K5xELjXKkehA5SR	model_update	succeeded	\N		{"total":0,"processed":0,"progress":100}	{"checked_channels":0,"changed_channels":0,"detected_add_models":0,"detected_remove_models":0,"failed_channels":0,"auto_added_models":0}		budgetloop-new-api-Ll4ilylC	1785038716	1785038716
8	systask_2Tg2CDY8zK6ZDvHxUwiOBEfSJdbwtcUe	model_update	succeeded	\N		{"total":0,"processed":0,"progress":100}	{"checked_channels":0,"changed_channels":0,"detected_add_models":0,"detected_remove_models":0,"failed_channels":0,"auto_added_models":0}		budgetloop-new-api-Ll4ilylC	1785033286	1785033286
9	systask_bPVsS2RZ1dNRaZiggUsu2SNsBWZjDYdb	model_update	succeeded	\N		{"total":0,"processed":0,"progress":100}	{"checked_channels":0,"changed_channels":0,"detected_add_models":0,"detected_remove_models":0,"failed_channels":0,"auto_added_models":0}		budgetloop-new-api-Ll4ilylC	1785035101	1785035101
15	systask_6Uqn1ZrKq6liH6Y44ojcUD638tFw0qYk	model_update	succeeded	\N		{"total":0,"processed":0,"progress":100}	{"checked_channels":0,"changed_channels":0,"detected_add_models":0,"detected_remove_models":0,"failed_channels":0,"auto_added_models":0}		budgetloop-new-api-Ll4ilylC	1785045916	1785045916
12	systask_3Ep7bUrZtYOCWyyQvutFOR8akHHvJ0pq	model_update	succeeded	\N		{"total":0,"processed":0,"progress":100}	{"checked_channels":0,"changed_channels":0,"detected_add_models":0,"detected_remove_models":0,"failed_channels":0,"auto_added_models":0}		budgetloop-new-api-Ll4ilylC	1785040516	1785040516
13	systask_i5Kfg89xfQiCkG7UX4odmTK35P1s2Jlo	model_update	succeeded	\N		{"total":0,"processed":0,"progress":100}	{"checked_channels":0,"changed_channels":0,"detected_add_models":0,"detected_remove_models":0,"failed_channels":0,"auto_added_models":0}		budgetloop-new-api-Ll4ilylC	1785042316	1785042316
14	systask_Ky8nHrfVesX7uwmdrF2DBkyyhxxkAvsU	model_update	succeeded	\N		{"total":0,"processed":0,"progress":100}	{"checked_channels":0,"changed_channels":0,"detected_add_models":0,"detected_remove_models":0,"failed_channels":0,"auto_added_models":0}		budgetloop-new-api-Ll4ilylC	1785044116	1785044116
16	systask_DXwuFHCF3yhIv7z6tmWKHUadVbrZDcr2	model_update	succeeded	\N		{"total":0,"processed":0,"progress":100}	{"checked_channels":0,"changed_channels":0,"detected_add_models":0,"detected_remove_models":0,"failed_channels":0,"auto_added_models":0}		budgetloop-new-api-Ll4ilylC	1785047716	1785047716
17	systask_VQucVPMcQhUxNbOFCNwRe53Fxu7ly5WM	model_update	succeeded	\N		{"total":0,"processed":0,"progress":100}	{"checked_channels":0,"changed_channels":0,"detected_add_models":0,"detected_remove_models":0,"failed_channels":0,"auto_added_models":0}		budgetloop-new-api-Ll4ilylC	1785049516	1785049516
18	systask_O4Lph8BJD4r4NA4SkralVHnY7ELb05uB	model_update	succeeded	\N		{"total":0,"processed":0,"progress":100}	{"checked_channels":0,"changed_channels":0,"detected_add_models":0,"detected_remove_models":0,"failed_channels":0,"auto_added_models":0}		budgetloop-new-api-Ll4ilylC	1785051316	1785051316
19	systask_itSiAKO5rmYXyHuTF7IYrC9Y4QAjwk4z	model_update	succeeded	\N		{"total":0,"processed":0,"progress":100}	{"checked_channels":0,"changed_channels":0,"detected_add_models":0,"detected_remove_models":0,"failed_channels":0,"auto_added_models":0}		budgetloop-new-api-Ll4ilylC	1785053116	1785053116
20	systask_2vaAgksVGCox7DQim37JJTtk4ZTURJ6b	model_update	succeeded	\N		{"total":0,"processed":0,"progress":100}	{"checked_channels":0,"changed_channels":0,"detected_add_models":0,"detected_remove_models":0,"failed_channels":0,"auto_added_models":0}		budgetloop-new-api-Ll4ilylC	1785054916	1785054916
\.


--
-- Data for Name: tasks; Type: TABLE DATA; Schema: public; Owner: budgetloop
--

COPY public.tasks (id, created_at, updated_at, task_id, platform, user_id, "group", channel_id, quota, action, status, fail_reason, submit_time, start_time, finish_time, progress, properties, private_data, data) FROM stdin;
\.


--
-- Data for Name: tokens; Type: TABLE DATA; Schema: public; Owner: budgetloop
--

COPY public.tokens (id, user_id, key, status, name, created_time, accessed_time, expired_time, remain_quota, unlimited_quota, model_limits_enabled, model_limits, allow_ips, used_quota, "group", cross_group_retry, deleted_at) FROM stdin;
\.


--
-- Data for Name: top_ups; Type: TABLE DATA; Schema: public; Owner: budgetloop
--

COPY public.top_ups (id, user_id, amount, money, trade_no, payment_method, payment_provider, create_time, complete_time, status) FROM stdin;
\.


--
-- Data for Name: two_fa_backup_codes; Type: TABLE DATA; Schema: public; Owner: budgetloop
--

COPY public.two_fa_backup_codes (id, user_id, code_hash, is_used, used_at, created_at, deleted_at) FROM stdin;
\.


--
-- Data for Name: two_fas; Type: TABLE DATA; Schema: public; Owner: budgetloop
--

COPY public.two_fas (id, user_id, secret, is_enabled, failed_attempts, locked_until, last_used_at, created_at, updated_at, deleted_at) FROM stdin;
\.


--
-- Data for Name: user_oauth_bindings; Type: TABLE DATA; Schema: public; Owner: budgetloop
--

COPY public.user_oauth_bindings (id, user_id, provider_id, provider_user_id, created_at) FROM stdin;
\.


--
-- Data for Name: user_subscriptions; Type: TABLE DATA; Schema: public; Owner: budgetloop
--

COPY public.user_subscriptions (id, user_id, plan_id, amount_total, amount_used, start_time, end_time, status, source, last_reset_time, next_reset_time, upgrade_group, prev_user_group, downgrade_group, allow_wallet_overflow, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: budgetloop
--

COPY public.users (id, username, password, display_name, role, status, email, github_id, discord_id, oidc_id, wechat_id, telegram_id, access_token, quota, used_quota, request_count, "group", aff_code, aff_count, aff_quota, aff_history, inviter_id, deleted_at, linux_do_id, setting, remark, stripe_customer, created_at, last_login_at) FROM stdin;
\.


--
-- Data for Name: vendors; Type: TABLE DATA; Schema: public; Owner: budgetloop
--

COPY public.vendors (id, name, description, icon, status, created_time, updated_time, deleted_at) FROM stdin;
\.


--
-- Name: authz_roles_id_seq; Type: SEQUENCE SET; Schema: public; Owner: budgetloop
--

SELECT pg_catalog.setval('public.authz_roles_id_seq', 8, true);


--
-- Name: casbin_rule_id_seq; Type: SEQUENCE SET; Schema: public; Owner: budgetloop
--

SELECT pg_catalog.setval('public.casbin_rule_id_seq', 12, true);


--
-- Name: channels_id_seq; Type: SEQUENCE SET; Schema: public; Owner: budgetloop
--

SELECT pg_catalog.setval('public.channels_id_seq', 1, false);


--
-- Name: checkins_id_seq; Type: SEQUENCE SET; Schema: public; Owner: budgetloop
--

SELECT pg_catalog.setval('public.checkins_id_seq', 1, false);


--
-- Name: custom_oauth_providers_id_seq; Type: SEQUENCE SET; Schema: public; Owner: budgetloop
--

SELECT pg_catalog.setval('public.custom_oauth_providers_id_seq', 1, false);


--
-- Name: logs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: budgetloop
--

SELECT pg_catalog.setval('public.logs_id_seq', 1, false);


--
-- Name: midjourneys_id_seq; Type: SEQUENCE SET; Schema: public; Owner: budgetloop
--

SELECT pg_catalog.setval('public.midjourneys_id_seq', 1, false);


--
-- Name: models_id_seq; Type: SEQUENCE SET; Schema: public; Owner: budgetloop
--

SELECT pg_catalog.setval('public.models_id_seq', 1, false);


--
-- Name: passkey_credentials_id_seq; Type: SEQUENCE SET; Schema: public; Owner: budgetloop
--

SELECT pg_catalog.setval('public.passkey_credentials_id_seq', 1, false);


--
-- Name: perf_metrics_id_seq; Type: SEQUENCE SET; Schema: public; Owner: budgetloop
--

SELECT pg_catalog.setval('public.perf_metrics_id_seq', 1, false);


--
-- Name: prefill_groups_id_seq; Type: SEQUENCE SET; Schema: public; Owner: budgetloop
--

SELECT pg_catalog.setval('public.prefill_groups_id_seq', 1, false);


--
-- Name: quota_data_id_seq; Type: SEQUENCE SET; Schema: public; Owner: budgetloop
--

SELECT pg_catalog.setval('public.quota_data_id_seq', 1, false);


--
-- Name: redemptions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: budgetloop
--

SELECT pg_catalog.setval('public.redemptions_id_seq', 1, false);


--
-- Name: setups_id_seq; Type: SEQUENCE SET; Schema: public; Owner: budgetloop
--

SELECT pg_catalog.setval('public.setups_id_seq', 1, false);


--
-- Name: subscription_orders_id_seq; Type: SEQUENCE SET; Schema: public; Owner: budgetloop
--

SELECT pg_catalog.setval('public.subscription_orders_id_seq', 1, false);


--
-- Name: subscription_plans_id_seq; Type: SEQUENCE SET; Schema: public; Owner: budgetloop
--

SELECT pg_catalog.setval('public.subscription_plans_id_seq', 1, false);


--
-- Name: subscription_pre_consume_records_id_seq; Type: SEQUENCE SET; Schema: public; Owner: budgetloop
--

SELECT pg_catalog.setval('public.subscription_pre_consume_records_id_seq', 1, false);


--
-- Name: system_tasks_id_seq; Type: SEQUENCE SET; Schema: public; Owner: budgetloop
--

SELECT pg_catalog.setval('public.system_tasks_id_seq', 20, true);


--
-- Name: tasks_id_seq; Type: SEQUENCE SET; Schema: public; Owner: budgetloop
--

SELECT pg_catalog.setval('public.tasks_id_seq', 1, false);


--
-- Name: tokens_id_seq; Type: SEQUENCE SET; Schema: public; Owner: budgetloop
--

SELECT pg_catalog.setval('public.tokens_id_seq', 1, false);


--
-- Name: top_ups_id_seq; Type: SEQUENCE SET; Schema: public; Owner: budgetloop
--

SELECT pg_catalog.setval('public.top_ups_id_seq', 1, false);


--
-- Name: two_fa_backup_codes_id_seq; Type: SEQUENCE SET; Schema: public; Owner: budgetloop
--

SELECT pg_catalog.setval('public.two_fa_backup_codes_id_seq', 1, false);


--
-- Name: two_fas_id_seq; Type: SEQUENCE SET; Schema: public; Owner: budgetloop
--

SELECT pg_catalog.setval('public.two_fas_id_seq', 1, false);


--
-- Name: user_oauth_bindings_id_seq; Type: SEQUENCE SET; Schema: public; Owner: budgetloop
--

SELECT pg_catalog.setval('public.user_oauth_bindings_id_seq', 1, false);


--
-- Name: user_subscriptions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: budgetloop
--

SELECT pg_catalog.setval('public.user_subscriptions_id_seq', 1, false);


--
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: budgetloop
--

SELECT pg_catalog.setval('public.users_id_seq', 1, false);


--
-- Name: vendors_id_seq; Type: SEQUENCE SET; Schema: public; Owner: budgetloop
--

SELECT pg_catalog.setval('public.vendors_id_seq', 1, false);


--
-- Name: abilities abilities_pkey; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.abilities
    ADD CONSTRAINT abilities_pkey PRIMARY KEY ("group", model, channel_id);


--
-- Name: authz_roles authz_roles_pkey; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.authz_roles
    ADD CONSTRAINT authz_roles_pkey PRIMARY KEY (id);


--
-- Name: casbin_rule casbin_rule_pkey; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.casbin_rule
    ADD CONSTRAINT casbin_rule_pkey PRIMARY KEY (id);


--
-- Name: channels channels_pkey; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.channels
    ADD CONSTRAINT channels_pkey PRIMARY KEY (id);


--
-- Name: checkins checkins_pkey; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.checkins
    ADD CONSTRAINT checkins_pkey PRIMARY KEY (id);


--
-- Name: custom_oauth_providers custom_oauth_providers_pkey; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.custom_oauth_providers
    ADD CONSTRAINT custom_oauth_providers_pkey PRIMARY KEY (id);


--
-- Name: prefill_groups idx_prefill_groups_name; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.prefill_groups
    ADD CONSTRAINT idx_prefill_groups_name UNIQUE (name);


--
-- Name: logs logs_pkey; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.logs
    ADD CONSTRAINT logs_pkey PRIMARY KEY (id);


--
-- Name: midjourneys midjourneys_pkey; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.midjourneys
    ADD CONSTRAINT midjourneys_pkey PRIMARY KEY (id);


--
-- Name: models models_pkey; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.models
    ADD CONSTRAINT models_pkey PRIMARY KEY (id);


--
-- Name: options options_pkey; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.options
    ADD CONSTRAINT options_pkey PRIMARY KEY (key);


--
-- Name: passkey_credentials passkey_credentials_pkey; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.passkey_credentials
    ADD CONSTRAINT passkey_credentials_pkey PRIMARY KEY (id);


--
-- Name: perf_metrics perf_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.perf_metrics
    ADD CONSTRAINT perf_metrics_pkey PRIMARY KEY (id);


--
-- Name: prefill_groups prefill_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.prefill_groups
    ADD CONSTRAINT prefill_groups_pkey PRIMARY KEY (id);


--
-- Name: quota_data quota_data_pkey; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.quota_data
    ADD CONSTRAINT quota_data_pkey PRIMARY KEY (id);


--
-- Name: redemptions redemptions_pkey; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.redemptions
    ADD CONSTRAINT redemptions_pkey PRIMARY KEY (id);


--
-- Name: setups setups_pkey; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.setups
    ADD CONSTRAINT setups_pkey PRIMARY KEY (id);


--
-- Name: subscription_orders subscription_orders_pkey; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.subscription_orders
    ADD CONSTRAINT subscription_orders_pkey PRIMARY KEY (id);


--
-- Name: subscription_orders subscription_orders_trade_no_key; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.subscription_orders
    ADD CONSTRAINT subscription_orders_trade_no_key UNIQUE (trade_no);


--
-- Name: subscription_plans subscription_plans_pkey; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.subscription_plans
    ADD CONSTRAINT subscription_plans_pkey PRIMARY KEY (id);


--
-- Name: subscription_pre_consume_records subscription_pre_consume_records_pkey; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.subscription_pre_consume_records
    ADD CONSTRAINT subscription_pre_consume_records_pkey PRIMARY KEY (id);


--
-- Name: system_instances system_instances_pkey; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.system_instances
    ADD CONSTRAINT system_instances_pkey PRIMARY KEY (node_name);


--
-- Name: system_task_locks system_task_locks_pkey; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.system_task_locks
    ADD CONSTRAINT system_task_locks_pkey PRIMARY KEY (type);


--
-- Name: system_tasks system_tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.system_tasks
    ADD CONSTRAINT system_tasks_pkey PRIMARY KEY (id);


--
-- Name: tasks tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_pkey PRIMARY KEY (id);


--
-- Name: tokens tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.tokens
    ADD CONSTRAINT tokens_pkey PRIMARY KEY (id);


--
-- Name: top_ups top_ups_pkey; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.top_ups
    ADD CONSTRAINT top_ups_pkey PRIMARY KEY (id);


--
-- Name: top_ups top_ups_trade_no_key; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.top_ups
    ADD CONSTRAINT top_ups_trade_no_key UNIQUE (trade_no);


--
-- Name: two_fa_backup_codes two_fa_backup_codes_pkey; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.two_fa_backup_codes
    ADD CONSTRAINT two_fa_backup_codes_pkey PRIMARY KEY (id);


--
-- Name: two_fas two_fas_pkey; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.two_fas
    ADD CONSTRAINT two_fas_pkey PRIMARY KEY (id);


--
-- Name: two_fas two_fas_user_id_key; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.two_fas
    ADD CONSTRAINT two_fas_user_id_key UNIQUE (user_id);


--
-- Name: user_oauth_bindings user_oauth_bindings_pkey; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.user_oauth_bindings
    ADD CONSTRAINT user_oauth_bindings_pkey PRIMARY KEY (id);


--
-- Name: user_subscriptions user_subscriptions_pkey; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.user_subscriptions
    ADD CONSTRAINT user_subscriptions_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- Name: vendors vendors_pkey; Type: CONSTRAINT; Schema: public; Owner: budgetloop
--

ALTER TABLE ONLY public.vendors
    ADD CONSTRAINT vendors_pkey PRIMARY KEY (id);


--
-- Name: idx_abilities_channel_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_abilities_channel_id ON public.abilities USING btree (channel_id);


--
-- Name: idx_abilities_priority; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_abilities_priority ON public.abilities USING btree (priority);


--
-- Name: idx_abilities_tag; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_abilities_tag ON public.abilities USING btree (tag);


--
-- Name: idx_abilities_weight; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_abilities_weight ON public.abilities USING btree (weight);


--
-- Name: idx_authz_roles_key; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE UNIQUE INDEX idx_authz_roles_key ON public.authz_roles USING btree (key);


--
-- Name: idx_casbin_rule; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_casbin_rule ON public.casbin_rule USING btree (ptype, v0, v1, v2, v3, v4, v5);


--
-- Name: idx_casbin_rule_unique; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE UNIQUE INDEX idx_casbin_rule_unique ON public.casbin_rule USING btree (ptype, v0, v1, v2, v3, v4, v5);


--
-- Name: idx_channels_name; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_channels_name ON public.channels USING btree (name);


--
-- Name: idx_channels_tag; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_channels_tag ON public.channels USING btree (tag);


--
-- Name: idx_created_at_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_created_at_id ON public.logs USING btree (created_at, id);


--
-- Name: idx_created_at_type; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_created_at_type ON public.logs USING btree (created_at, type);


--
-- Name: idx_custom_oauth_providers_slug; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE UNIQUE INDEX idx_custom_oauth_providers_slug ON public.custom_oauth_providers USING btree (slug);


--
-- Name: idx_logs_channel_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_logs_channel_id ON public.logs USING btree (channel_id);


--
-- Name: idx_logs_group; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_logs_group ON public.logs USING btree ("group");


--
-- Name: idx_logs_ip; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_logs_ip ON public.logs USING btree (ip);


--
-- Name: idx_logs_model_name; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_logs_model_name ON public.logs USING btree (model_name);


--
-- Name: idx_logs_request_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_logs_request_id ON public.logs USING btree (request_id);


--
-- Name: idx_logs_token_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_logs_token_id ON public.logs USING btree (token_id);


--
-- Name: idx_logs_token_name; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_logs_token_name ON public.logs USING btree (token_name);


--
-- Name: idx_logs_upstream_request_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_logs_upstream_request_id ON public.logs USING btree (upstream_request_id);


--
-- Name: idx_logs_user_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_logs_user_id ON public.logs USING btree (user_id);


--
-- Name: idx_logs_username; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_logs_username ON public.logs USING btree (username);


--
-- Name: idx_midjourneys_action; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_midjourneys_action ON public.midjourneys USING btree (action);


--
-- Name: idx_midjourneys_finish_time; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_midjourneys_finish_time ON public.midjourneys USING btree (finish_time);


--
-- Name: idx_midjourneys_mj_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_midjourneys_mj_id ON public.midjourneys USING btree (mj_id);


--
-- Name: idx_midjourneys_progress; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_midjourneys_progress ON public.midjourneys USING btree (progress);


--
-- Name: idx_midjourneys_start_time; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_midjourneys_start_time ON public.midjourneys USING btree (start_time);


--
-- Name: idx_midjourneys_status; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_midjourneys_status ON public.midjourneys USING btree (status);


--
-- Name: idx_midjourneys_submit_time; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_midjourneys_submit_time ON public.midjourneys USING btree (submit_time);


--
-- Name: idx_midjourneys_user_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_midjourneys_user_id ON public.midjourneys USING btree (user_id);


--
-- Name: idx_models_deleted_at; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_models_deleted_at ON public.models USING btree (deleted_at);


--
-- Name: idx_models_vendor_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_models_vendor_id ON public.models USING btree (vendor_id);


--
-- Name: idx_passkey_credentials_credential_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE UNIQUE INDEX idx_passkey_credentials_credential_id ON public.passkey_credentials USING btree (credential_id);


--
-- Name: idx_passkey_credentials_deleted_at; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_passkey_credentials_deleted_at ON public.passkey_credentials USING btree (deleted_at);


--
-- Name: idx_passkey_credentials_user_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE UNIQUE INDEX idx_passkey_credentials_user_id ON public.passkey_credentials USING btree (user_id);


--
-- Name: idx_perf_bucket_ts; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_perf_bucket_ts ON public.perf_metrics USING btree (bucket_ts);


--
-- Name: idx_perf_model_group_bucket; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE UNIQUE INDEX idx_perf_model_group_bucket ON public.perf_metrics USING btree (model_name, "group", bucket_ts);


--
-- Name: idx_prefill_groups_deleted_at; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_prefill_groups_deleted_at ON public.prefill_groups USING btree (deleted_at);


--
-- Name: idx_prefill_groups_type; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_prefill_groups_type ON public.prefill_groups USING btree (type);


--
-- Name: idx_qdt_created_at; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_qdt_created_at ON public.quota_data USING btree (created_at);


--
-- Name: idx_qdt_model_user_name; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_qdt_model_user_name ON public.quota_data USING btree (model_name, username);


--
-- Name: idx_quota_data_channel_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_quota_data_channel_id ON public.quota_data USING btree (channel_id);


--
-- Name: idx_quota_data_node_name; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_quota_data_node_name ON public.quota_data USING btree (node_name);


--
-- Name: idx_quota_data_token_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_quota_data_token_id ON public.quota_data USING btree (token_id);


--
-- Name: idx_quota_data_use_group; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_quota_data_use_group ON public.quota_data USING btree (use_group);


--
-- Name: idx_quota_data_user_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_quota_data_user_id ON public.quota_data USING btree (user_id);


--
-- Name: idx_redemptions_deleted_at; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_redemptions_deleted_at ON public.redemptions USING btree (deleted_at);


--
-- Name: idx_redemptions_key; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE UNIQUE INDEX idx_redemptions_key ON public.redemptions USING btree (key);


--
-- Name: idx_redemptions_name; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_redemptions_name ON public.redemptions USING btree (name);


--
-- Name: idx_subscription_orders_plan_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_subscription_orders_plan_id ON public.subscription_orders USING btree (plan_id);


--
-- Name: idx_subscription_orders_trade_no; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_subscription_orders_trade_no ON public.subscription_orders USING btree (trade_no);


--
-- Name: idx_subscription_orders_user_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_subscription_orders_user_id ON public.subscription_orders USING btree (user_id);


--
-- Name: idx_subscription_pre_consume_records_request_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE UNIQUE INDEX idx_subscription_pre_consume_records_request_id ON public.subscription_pre_consume_records USING btree (request_id);


--
-- Name: idx_subscription_pre_consume_records_status; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_subscription_pre_consume_records_status ON public.subscription_pre_consume_records USING btree (status);


--
-- Name: idx_subscription_pre_consume_records_updated_at; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_subscription_pre_consume_records_updated_at ON public.subscription_pre_consume_records USING btree (updated_at);


--
-- Name: idx_subscription_pre_consume_records_user_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_subscription_pre_consume_records_user_id ON public.subscription_pre_consume_records USING btree (user_id);


--
-- Name: idx_subscription_pre_consume_records_user_subscription_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_subscription_pre_consume_records_user_subscription_id ON public.subscription_pre_consume_records USING btree (user_subscription_id);


--
-- Name: idx_system_instances_created_at; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_system_instances_created_at ON public.system_instances USING btree (created_at);


--
-- Name: idx_system_instances_last_seen_at; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_system_instances_last_seen_at ON public.system_instances USING btree (last_seen_at);


--
-- Name: idx_system_instances_started_at; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_system_instances_started_at ON public.system_instances USING btree (started_at);


--
-- Name: idx_system_instances_updated_at; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_system_instances_updated_at ON public.system_instances USING btree (updated_at);


--
-- Name: idx_system_task_locks_locked_by; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_system_task_locks_locked_by ON public.system_task_locks USING btree (locked_by);


--
-- Name: idx_system_task_locks_locked_until; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_system_task_locks_locked_until ON public.system_task_locks USING btree (locked_until);


--
-- Name: idx_system_task_locks_task_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_system_task_locks_task_id ON public.system_task_locks USING btree (task_id);


--
-- Name: idx_system_task_locks_updated_at; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_system_task_locks_updated_at ON public.system_task_locks USING btree (updated_at);


--
-- Name: idx_system_tasks_active_key; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE UNIQUE INDEX idx_system_tasks_active_key ON public.system_tasks USING btree (active_key);


--
-- Name: idx_system_tasks_created_at; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_system_tasks_created_at ON public.system_tasks USING btree (created_at);


--
-- Name: idx_system_tasks_locked_by; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_system_tasks_locked_by ON public.system_tasks USING btree (locked_by);


--
-- Name: idx_system_tasks_status; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_system_tasks_status ON public.system_tasks USING btree (status);


--
-- Name: idx_system_tasks_task_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE UNIQUE INDEX idx_system_tasks_task_id ON public.system_tasks USING btree (task_id);


--
-- Name: idx_system_tasks_type; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_system_tasks_type ON public.system_tasks USING btree (type);


--
-- Name: idx_system_tasks_updated_at; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_system_tasks_updated_at ON public.system_tasks USING btree (updated_at);


--
-- Name: idx_tasks_action; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_tasks_action ON public.tasks USING btree (action);


--
-- Name: idx_tasks_channel_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_tasks_channel_id ON public.tasks USING btree (channel_id);


--
-- Name: idx_tasks_created_at; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_tasks_created_at ON public.tasks USING btree (created_at);


--
-- Name: idx_tasks_finish_time; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_tasks_finish_time ON public.tasks USING btree (finish_time);


--
-- Name: idx_tasks_platform; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_tasks_platform ON public.tasks USING btree (platform);


--
-- Name: idx_tasks_progress; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_tasks_progress ON public.tasks USING btree (progress);


--
-- Name: idx_tasks_start_time; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_tasks_start_time ON public.tasks USING btree (start_time);


--
-- Name: idx_tasks_status; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_tasks_status ON public.tasks USING btree (status);


--
-- Name: idx_tasks_submit_time; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_tasks_submit_time ON public.tasks USING btree (submit_time);


--
-- Name: idx_tasks_task_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_tasks_task_id ON public.tasks USING btree (task_id);


--
-- Name: idx_tasks_user_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_tasks_user_id ON public.tasks USING btree (user_id);


--
-- Name: idx_tokens_deleted_at; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_tokens_deleted_at ON public.tokens USING btree (deleted_at);


--
-- Name: idx_tokens_key; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE UNIQUE INDEX idx_tokens_key ON public.tokens USING btree (key);


--
-- Name: idx_tokens_name; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_tokens_name ON public.tokens USING btree (name);


--
-- Name: idx_tokens_user_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_tokens_user_id ON public.tokens USING btree (user_id);


--
-- Name: idx_top_ups_trade_no; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_top_ups_trade_no ON public.top_ups USING btree (trade_no);


--
-- Name: idx_top_ups_user_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_top_ups_user_id ON public.top_ups USING btree (user_id);


--
-- Name: idx_two_fa_backup_codes_deleted_at; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_two_fa_backup_codes_deleted_at ON public.two_fa_backup_codes USING btree (deleted_at);


--
-- Name: idx_two_fa_backup_codes_user_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_two_fa_backup_codes_user_id ON public.two_fa_backup_codes USING btree (user_id);


--
-- Name: idx_two_fas_deleted_at; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_two_fas_deleted_at ON public.two_fas USING btree (deleted_at);


--
-- Name: idx_two_fas_user_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_two_fas_user_id ON public.two_fas USING btree (user_id);


--
-- Name: idx_user_checkin_date; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE UNIQUE INDEX idx_user_checkin_date ON public.checkins USING btree (user_id, checkin_date);


--
-- Name: idx_user_id_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_user_id_id ON public.logs USING btree (user_id, id);


--
-- Name: idx_user_sub_active; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_user_sub_active ON public.user_subscriptions USING btree (user_id, status, end_time);


--
-- Name: idx_user_subscriptions_end_time; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_user_subscriptions_end_time ON public.user_subscriptions USING btree (end_time);


--
-- Name: idx_user_subscriptions_next_reset_time; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_user_subscriptions_next_reset_time ON public.user_subscriptions USING btree (next_reset_time);


--
-- Name: idx_user_subscriptions_plan_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_user_subscriptions_plan_id ON public.user_subscriptions USING btree (plan_id);


--
-- Name: idx_user_subscriptions_status; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_user_subscriptions_status ON public.user_subscriptions USING btree (status);


--
-- Name: idx_user_subscriptions_user_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_user_subscriptions_user_id ON public.user_subscriptions USING btree (user_id);


--
-- Name: idx_users_access_token; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE UNIQUE INDEX idx_users_access_token ON public.users USING btree (access_token);


--
-- Name: idx_users_aff_code; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE UNIQUE INDEX idx_users_aff_code ON public.users USING btree (aff_code);


--
-- Name: idx_users_deleted_at; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_users_deleted_at ON public.users USING btree (deleted_at);


--
-- Name: idx_users_discord_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_users_discord_id ON public.users USING btree (discord_id);


--
-- Name: idx_users_display_name; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_users_display_name ON public.users USING btree (display_name);


--
-- Name: idx_users_email; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_users_email ON public.users USING btree (email);


--
-- Name: idx_users_git_hub_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_users_git_hub_id ON public.users USING btree (github_id);


--
-- Name: idx_users_inviter_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_users_inviter_id ON public.users USING btree (inviter_id);


--
-- Name: idx_users_linux_do_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_users_linux_do_id ON public.users USING btree (linux_do_id);


--
-- Name: idx_users_oidc_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_users_oidc_id ON public.users USING btree (oidc_id);


--
-- Name: idx_users_stripe_customer; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_users_stripe_customer ON public.users USING btree (stripe_customer);


--
-- Name: idx_users_telegram_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_users_telegram_id ON public.users USING btree (telegram_id);


--
-- Name: idx_users_username; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_users_username ON public.users USING btree (username);


--
-- Name: idx_users_we_chat_id; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_users_we_chat_id ON public.users USING btree (wechat_id);


--
-- Name: idx_vendors_deleted_at; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX idx_vendors_deleted_at ON public.vendors USING btree (deleted_at);


--
-- Name: index_username_model_name; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE INDEX index_username_model_name ON public.logs USING btree (model_name, username);


--
-- Name: uk_model_name_delete_at; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE UNIQUE INDEX uk_model_name_delete_at ON public.models USING btree (model_name, deleted_at);


--
-- Name: uk_prefill_name; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE UNIQUE INDEX uk_prefill_name ON public.prefill_groups USING btree (name) WHERE (deleted_at IS NULL);


--
-- Name: uk_vendor_name_delete_at; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE UNIQUE INDEX uk_vendor_name_delete_at ON public.vendors USING btree (name, deleted_at);


--
-- Name: ux_provider_userid; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE UNIQUE INDEX ux_provider_userid ON public.user_oauth_bindings USING btree (provider_id, provider_user_id);


--
-- Name: ux_user_provider; Type: INDEX; Schema: public; Owner: budgetloop
--

CREATE UNIQUE INDEX ux_user_provider ON public.user_oauth_bindings USING btree (user_id, provider_id);


--
-- PostgreSQL database dump complete
--

\unrestrict 47kr0bVCTTLMdY2fTaFw3BwOrE4HSFec0keCIthjDkKioZDwucRQJ8Nqd9hg5Sb

