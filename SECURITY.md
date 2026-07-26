# Security Policy

## Scope

Family Hub is a self-hosted family application. It is provided as an actively developed personal project and has not
received an independent security audit. Deployers are responsible for protecting the host, database, photo storage,
backups, environment files, and external services used by their installation.

Do not use real passwords, private keys, photo originals, database backups, tunnel tokens, or other sensitive data in
issues, pull requests, test fixtures, or public logs.

## Reporting a vulnerability

Please do not disclose suspected vulnerabilities in a public issue. Contact the repository maintainer through a private
channel or a private GitHub Security Advisory, if that feature is enabled for the repository. Include:

- the affected commit, version, or deployment configuration;
- a concise description of the impact;
- reproduction steps or a minimal proof of concept; and
- any suggested mitigation.

Please allow reasonable time for investigation and a fix before public disclosure. Do not include family photos, credentials,
session cookies, or other personal data in a report.

## Supported versions

There are currently no formal long-term support releases. Security fixes are applied to the active development branch when
practical. Operators should deploy only reviewed commits and keep dependencies, the operating system, PostgreSQL, Caddy,
and Cloudflare Tunnel up to date.
