import logging
import signal
from typing import Any

from quixstreams import Application
from quixstreams.sinks.base.item import SinkItem
from quixstreams.sinks.community.elasticsearch import ElasticsearchSink

from .config import get_settings
