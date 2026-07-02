"""
Historical marker only.

Interactive voice features do not use a Django websocket bridge. The active
architecture is backend Realtime client-secret minting plus browser WebRTC, and
server-side explanation audio uses `english_course.utils.realtime_tts`.
"""

# No websocket consumers are intentionally exposed from this module.
