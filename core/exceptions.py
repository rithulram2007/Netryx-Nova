class NetryxError(Exception):
    """Base exception for all Netryx Nova pipeline errors."""


class IndexLoadError(NetryxError):
    """Raised when a .netryx bundle cannot be loaded or parsed."""


class IndexNotFoundError(NetryxError):
    """Raised when no index is loaded and a search is attempted."""


class EngineUnavailableError(NetryxError):
    """Raised when the requested execution engine is not available."""


class ModelLoadError(NetryxError):
    """Raised when a model (MegaLoc, MASt3R) fails to load."""


class SearchError(NetryxError):
    """Raised when a search job encounters a runtime error."""


class TileDownloadError(NetryxError):
    """Raised when Google Street View tile fetching fails after all retries."""


class HubConnectionError(NetryxError):
    """Raised when the Hugging Face Hub connection fails."""
