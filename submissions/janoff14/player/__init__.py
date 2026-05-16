"""Fullscreen looping promo video player.

The player is the main process of the kiosk system. The recognition worker
and Telegram bot will be spawned later from the supervisor (Story 3.1) and
will deliver greeting events through a queue (Story 2.4).
"""
