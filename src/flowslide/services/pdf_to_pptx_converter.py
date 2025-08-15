"""
PDF to PPTX Converter Service for FlowSlide
Uses Apryse SDK to convert PDF files to PowerPoint presentations
"""

import logging
import os
import platform
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Optional, Tuple

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class SDKDownloadManager:
    """Manages automatic download and extraction of Apryse SDK files"""

    # SDK download URLs for different platforms
    SDK_URLS = {
        "windows": "https://www.pdftron.com/downloads/StructuredOutputWindows.zip",
        "linux": "https://pdftron.s3.amazonaws.com/downloads/StructuredOutputLinux.tar.gz",
        "macos": "https://pdftron.s3.amazonaws.com/downloads/StructuredOutputMac.zip",
    }

    def __init__(self, lib_dir: Path):
        self.lib_dir = lib_dir
        self.platform_name = self._get_platform_name()
        self.platform_dir = lib_dir / self._get_platform_dir_name()

    def _get_platform_name(self) -> str:
        """Get normalized platform name"""
        system = platform.system().lower()
        if system == "windows":
            return "windows"
        elif system == "linux":
            return "linux"
        elif system == "darwin":
            return "macos"
        else:
            # Default to linux for unknown platforms
            return "linux"

    def _get_platform_dir_name(self) -> str:
        """Get platform directory name in lib folder"""
        if self.platform_name == "windows":
            return "Windows"
        elif self.platform_name == "linux":
            return "Linux"
        elif self.platform_name == "macos":
            return "MacOS"
        else:
            return "Linux"

    def is_sdk_available(self) -> bool:
        """Check if SDK files are available for current platform"""
        if not self.platform_dir.exists():
            return False

        # Check for key SDK files based on platform
        if self.platform_name == "windows":
            # Windows SDK has nested structure: Windows/Lib/Windows/StructuredOutput.exe
            nested_windows_dir = self.platform_dir / "Lib" / "Windows"
            required_files = [nested_windows_dir / "StructuredOutput.exe"]
        else:
            required_files = [self.platform_dir / "StructuredOutput"]

        for file_path in required_files:
            if not file_path.exists():
                return False

        return True

    def download_and_extract_sdk(self) -> bool:
        """Download and extract SDK for current platform"""
        if self.platform_name not in self.SDK_URLS:
            logger.error(
                f"No SDK download URL available for platform: {self.platform_name}"
            )
            return False

        url = self.SDK_URLS[self.platform_name]
        logger.info(f"Downloading SDK for {self.platform_name} from: {url}")

        try:
            # Create lib directory if it doesn't exist
            self.lib_dir.mkdir(parents=True, exist_ok=True)

            # Download the file
            response = requests.get(url, stream=True, timeout=300)
            response.raise_for_status()

            # Determine file extension and create temporary file
            if url.endswith(".zip"):
                suffix = ".zip"
            elif url.endswith(".tar.gz"):
                suffix = ".tar.gz"
            else:
                suffix = ".zip"  # Default to zip

            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
                temp_path = temp_file.name

                # Download with progress logging
                total_size = int(response.headers.get("content-length", 0))
                downloaded = 0

                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        temp_file.write(chunk)
                        downloaded += len(chunk)

                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            if downloaded % (1024 * 1024) == 0:  # Log every MB
                                logger.info(f"Download progress: {progress:.1f}%")

            logger.info(f"Download completed: {temp_path}")

            # Extract the downloaded file
            success = self._extract_file(temp_path)

            # Clean up temporary file
            try:
                os.unlink(temp_path)
            except:
                pass

            return success

        except Exception as e:
            logger.error(f"Failed to download SDK: {e}")
            return False

    def _extract_file(self, file_path: str) -> bool:
        """Extract downloaded SDK file"""
        try:
            logger.info(f"Extracting SDK to: {self.platform_dir}")

            # Create platform directory
            self.platform_dir.mkdir(parents=True, exist_ok=True)

            if file_path.endswith(".zip"):
                with zipfile.ZipFile(file_path, "r") as zip_ref:
                    zip_ref.extractall(self.platform_dir)
            elif file_path.endswith(".tar.gz"):
                with tarfile.open(file_path, "r:gz") as tar_ref:
                    tar_ref.extractall(self.platform_dir)
            else:
                logger.error(f"Unsupported file format: {file_path}")
                return False

            logger.info("SDK extraction completed successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to extract SDK: {e}")
            return False

    def ensure_sdk_available(self) -> bool:
        """Ensure SDK is available, download if necessary"""
        if self.is_sdk_available():
            logger.info(f"SDK already available for {self.platform_name}")
            return True

        logger.info(f"SDK not found for {self.platform_name}, downloading...")
        return self.download_and_extract_sdk()


class PDFToPPTXConverter:
    """Converts PDF files to PPTX using Apryse SDK"""

    def __init__(self):
        self._sdk_initialized = False
        self._sdk_available = None

        # Initialize SDK download manager
        current_file = Path(__file__).resolve()
        project_root = (
            current_file.parent.parent.parent.parent
        )  # Go up from services -> flowslide -> src -> project_root
        lib_dir = project_root / "lib"
        self.sdk_manager = SDKDownloadManager(lib_dir)

    @property
    def license_key(self):
        """Dynamically get license key to ensure latest config"""
        from ..core.config import ai_config

        return ai_config.apryse_license_key or "your_apryse_license_key_here"

    def _check_sdk_availability(self) -> bool:
        """Check if Apryse SDK is available and can be initialized"""
        if self._sdk_available is not None:
            return self._sdk_available

        # First, ensure SDK files are downloaded
        if not self.sdk_manager.ensure_sdk_available():
            self._sdk_available = False
            logger.error("Failed to download or extract SDK files")
            return False

        try:
            from apryse_sdk.PDFNetPython import (Convert, PDFNet,
                                                 StructuredOutputModule)

            self._sdk_available = True
            logger.info("Apryse SDK is available")
            return True
        except ImportError as e:
            self._sdk_available = False
            logger.warning(f"Apryse SDK not available: {e}")
            logger.warning(
                "SDK files may be downloaded but Python package is not installed"
            )
            return False

    def _initialize_sdk(self) -> bool:
        """Initialize Apryse SDK with license key"""
        if self._sdk_initialized:
            return True

        if not self._check_sdk_availability():
            return False

        try:
            from apryse_sdk.PDFNetPython import PDFNet, StructuredOutputModule

            # Initialize PDFNet with license key
            PDFNet.Initialize(self.license_key)

            # Use SDK manager to get the correct platform directory
            platform_dir = self.sdk_manager.platform_dir

            if self.sdk_manager.platform_name == "windows":
                sdk_resource_dir = platform_dir / "Lib/Windows"
            elif self.sdk_manager.platform_name == "linux":
                sdk_resource_dir = platform_dir / "Lib/Linux"
            elif self.sdk_manager.platform_name == "macos":
                sdk_resource_dir = platform_dir / "Lib/MacOS"
            else:
                logger.error(f"Unsupported platform: {self.sdk_manager.platform_name}")
                return False

            # Add resource search path for the downloaded SDK
            if sdk_resource_dir.exists():
                PDFNet.AddResourceSearchPath(str(sdk_resource_dir))
                logger.info(f"Added SDK resource search path: {sdk_resource_dir}")
            else:
                logger.error(f"SDK resource directory not found: {sdk_resource_dir}")
                return False

            # Check if Structured Output module is available
            if not StructuredOutputModule.IsModuleAvailable():
                logger.error("PDFTron SDK Structured Output module not available")
                logger.error(
                    "The Structured Output module is required for PDF to PowerPoint conversion"
                )
                logger.error("Please ensure the module is installed and accessible")
                return False

            self._sdk_initialized = True
            logger.info("Apryse SDK initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Apryse SDK: {e}")
            return False

    def reload_config(self):
        """Reload configuration and reinitialize SDK if needed"""
        logger.info("Reloading PDF to PPTX converter configuration...")
        # Force reinitialization with new license key
        self._sdk_initialized = False
        return self._initialize_sdk()

    def is_available(self) -> bool:
        """Check if the converter is available and ready to use"""
        return self._check_sdk_availability() and self._initialize_sdk()

    def convert_pdf_to_pptx(
        self, pdf_path: str, output_path: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Convert PDF file to PPTX format

        Args:
            pdf_path: Path to the input PDF file
            output_path: Path for the output PPTX file (optional, will generate if not provided)

        Returns:
            Tuple of (success: bool, output_path: str)
        """
        if not self.is_available():
            error_msg = "PDF to PPTX converter is not available. Please check Apryse SDK installation and license."
            logger.error(error_msg)
            return False, error_msg

        # Validate input file
        if not os.path.exists(pdf_path):
            error_msg = f"Input PDF file not found: {pdf_path}"
            logger.error(error_msg)
            return False, error_msg

        # Generate output path if not provided
        if output_path is None:
            pdf_name = Path(pdf_path).stem
            output_path = str(Path(pdf_path).parent / f"{pdf_name}.pptx")

        try:
            from apryse_sdk.PDFNetPython import Convert

            logger.info(f"Converting PDF to PowerPoint: {pdf_path} -> {output_path}")

            # Perform the conversion
            Convert.ToPowerPoint(pdf_path, output_path)

            # Verify output file was created
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                logger.info(f"PDF to PPTX conversion successful: {output_path}")
                return True, output_path
            else:
                error_msg = (
                    "Conversion completed but output file is empty or not created"
                )
                logger.error(error_msg)
                return False, error_msg

        except Exception as e:
            error_msg = f"PDF to PPTX conversion failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def convert_with_temp_pdf(
        self, pdf_content: bytes, output_filename: str = "converted.pptx"
    ) -> Tuple[bool, str, str]:
        """
        Convert PDF content to PPTX using temporary files

        Args:
            pdf_content: PDF file content as bytes
            output_filename: Desired output filename

        Returns:
            Tuple of (success: bool, output_path: str, error_message: str)
        """
        temp_pdf_path = None
        temp_pptx_path = None

        try:
            # Create temporary PDF file
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_pdf:
                temp_pdf.write(pdf_content)
                temp_pdf_path = temp_pdf.name

            # Create temporary PPTX file path with desired filename
            temp_dir = tempfile.gettempdir()
            # Use the provided output_filename for the temporary file
            base_name = Path(output_filename).stem
            temp_pptx_path = os.path.join(temp_dir, f"{base_name}_{os.getpid()}.pptx")

            # Perform conversion
            success, result = self.convert_pdf_to_pptx(temp_pdf_path, temp_pptx_path)

            if success:
                return True, temp_pptx_path, ""
            else:
                return False, "", result

        except Exception as e:
            error_msg = f"Temporary file conversion failed: {str(e)}"
            logger.error(error_msg)
            return False, "", error_msg

        finally:
            # Clean up temporary PDF file
            if temp_pdf_path and os.path.exists(temp_pdf_path):
                try:
                    os.unlink(temp_pdf_path)
                except:
                    pass

    def cleanup_temp_file(self, file_path: str):
        """Clean up temporary file"""
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
                logger.debug(f"Cleaned up temporary file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up temporary file {file_path}: {e}")

    def __del__(self):
        """Cleanup when converter is destroyed"""
        if self._sdk_initialized:
            try:
                from apryse_sdk.PDFNetPython import PDFNet

                PDFNet.Terminate()
                logger.debug("Apryse SDK terminated")
            except:
                pass


# Global converter instance
_converter_instance = None


def get_pdf_to_pptx_converter() -> PDFToPPTXConverter:
    """Get the global PDF to PPTX converter instance"""
    global _converter_instance
    if _converter_instance is None:
        _converter_instance = PDFToPPTXConverter()
    return _converter_instance


def reload_pdf_to_pptx_converter():
    """Reload PDF to PPTX converter configuration"""
    global _converter_instance
    if _converter_instance is not None:
        try:
            _converter_instance.reload_config()
            logger.info("PDF to PPTX converter configuration reloaded successfully")
        except Exception as e:
            logger.warning(f"Failed to reload PDF to PPTX converter config: {e}")
            # If reload fails, recreate the converter
            _converter_instance = None
