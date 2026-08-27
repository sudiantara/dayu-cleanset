# Dayu Cleanset Laundry

Laundry management system for Dayu Cleanset, built with FastAPI, PostgreSQL, React, Nginx, Docker Compose, and n8n/Telegram integrations.

## Current architecture

- `backend/` — FastAPI API
- `frontend/` — React/Vite frontend
- `backend/migrations/` — PostgreSQL schema migrations
- `docker-compose.yml` — application stack
- `.env` — local secrets (**never commit this file**)
- `.env.example` — safe configuration template

## Order model

- Customer identity/contact
- Hotel/Villa and room stored per order
- Service speed: `NORMAL` or `EXPRESS`
- Requested finish time
- Instagram + Google Review promo
- Optional negotiated/special discount
- Payment status: `UNPAID`, `PARTIAL`, `PAID`
- Laundry status workflow
- n8n/Telegram notifications

## Pricing

- NORMAL: Rp30.000 / KG — target up to 1 day
- EXPRESS: Rp55.000 / KG — target under 6 hours
- Promo: 5% when Instagram follow + Google Maps review requirements are both met
- Special discount: optional nominal discount for negotiated pricing

## Security

Never commit database passwords, tokens, webhook secrets, SSH keys, production `.env`, or database dumps containing customer data.

## Deployment

Production runs with Docker Compose. The existing server source should be synchronized into this repository before GitHub becomes the source of truth for deployment.
