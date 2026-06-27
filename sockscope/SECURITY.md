# Security Policy

## Reporting something

If you think you've found a security issue in `sockscope`, please don't open a public GitHub issue for it. Email the maintainers instead with:

- A short description of what's wrong
- Steps to reproduce it
- The version of `sockscope` and the Linux distribution you saw it on

We'll try to reply within a few days, and for anything we can confirm we aim to have a fix or a workaround out within about two weeks.

## What's in scope

`sockscope` is a read-only tool. It reads `/proc`, doesn't open network sockets, doesn't change any system state, and doesn't need privileges beyond what `/proc` access already gives you. If you find something that doesn't match that description, we'd like to hear about it.

## What's not

A couple of things we don't consider security issues:

- Problems that only show up when an attacker already has the same privileges as the target process.
- Information that `/proc` already exposes to whoever is running `sockscope` — the same things you'd see from `ps`, `ss`, or `lsof`.
