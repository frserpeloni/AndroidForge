"""API local da Plataforma SERMAX, com projetos persistentes e histórico SQLite."""
from __future__ import annotations

import importlib
import json
import os
import queue
import re
import sqlite3
import sys
import threading
import urllib.error
import urllib.request
import uuid
from contextlib import suppress
# Restante do código permanece inalterado
