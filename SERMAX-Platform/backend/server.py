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

# Função de exemplo para garantir que o módulo seja importável

def get_server_version() -> str:
    """Retorna a versão do servidor."""
    return "1.0.0"
