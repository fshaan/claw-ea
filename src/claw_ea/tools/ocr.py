"""ocr_image MCP tool — local OCR via macOS Vision framework."""
import base64

try:
    from Vision import VNRecognizeTextRequest, VNImageRequestHandler
    from Foundation import NSData
    VISION_AVAILABLE = True
except ImportError:
    VISION_AVAILABLE = False


def _run_ocr(image_data: bytes) -> str:
    """Run OCR using macOS Vision framework. Returns extracted text."""
    ns_data = NSData.dataWithBytes_length_(image_data, len(image_data))
    handler = VNImageRequestHandler.alloc().initWithData_options_(ns_data, None)

    request = VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLanguages_(["zh-Hans", "en"])
    request.setRecognitionLevel_(1)  # VNRequestTextRecognitionLevelAccurate

    success, error = handler.performRequests_error_([request], None)
    if not success:
        raise RuntimeError(f"Vision OCR failed: {error}")

    results = request.results()
    lines = []
    for observation in results:
        candidate = observation.topCandidates_(1)
        if candidate:
            lines.append(candidate[0].string())

    return "\n".join(lines)


def ocr_image_impl(image_content: str, filename: str) -> dict:
    """Core logic for ocr_image."""
    try:
        image_data = base64.b64decode(image_content, validate=True)
    except Exception as e:
        raise ValueError(f"Invalid base64 image content: {e}") from e

    if not VISION_AVAILABLE:
        raise RuntimeError(
            "macOS Vision framework not available. "
            "ocr_image requires macOS with pyobjc-framework-Vision."
        )

    text = _run_ocr(image_data)
    return {
        "extracted_text": text,
        "language": "zh-Hans+en",
    }


def register(mcp_instance):
    """Register ocr_image tool."""

    @mcp_instance.tool()
    async def ocr_image(image_content: str, filename: str) -> dict:
        """Extract text from an image using local OCR (macOS Vision framework).

        Use this tool only when the agent's LLM does not support vision/multimodal input.
        If the LLM can see images directly, prefer that over this tool.

        Args:
            image_content: Base64-encoded image data (PNG, JPEG, etc.)
            filename: Original filename for reference

        Returns:
            extracted_text: OCR-extracted text content
            language: Recognition languages used
        """
        return ocr_image_impl(image_content, filename)
