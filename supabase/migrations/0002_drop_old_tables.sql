-- Drop all legacy QuantHub tables (run manually after confirming 0001 is applied).
-- These tables are no longer used by the swing screener.

drop table if exists backtest_results cascade;
drop table if exists strategy_runs cascade;
drop table if exists portfolios cascade;
drop table if exists user_ai_keys cascade;
drop table if exists user_feature_trials cascade;
drop table if exists user_usage_counters cascade;
drop table if exists user_subscriptions cascade;
drop table if exists user_disclaimer_acceptances cascade;
drop table if exists profiles cascade;
