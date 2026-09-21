"""SAR calibration and despeckling — parameter-fed, no hardcoded sensor constants."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import uniform_filter


class SARCalibrationError(ValueError):
    """Raised when required calibration parameters are missing or invalid."""


def calibrate(
    array: NDArray,
    calibration_factor: float,
    incidence_angle_rad: float,
) -> NDArray:
    """Apply radiometric calibration to a SAR DN array.

    Parameters
    ----------
    array:
        Raw DN values (float or int array).
    calibration_factor:
        Sensor-specific calibration constant — must be sourced from product metadata.
    incidence_angle_rad:
        Local incidence angle in radians — must be sourced from product metadata.

    Returns
    -------
    Calibrated backscatter (linear scale, float32).
    """
    if calibration_factor <= 0:
        raise SARCalibrationError("calibration_factor must be > 0.")
    if not (0 < incidence_angle_rad < np.pi / 2):
        raise SARCalibrationError("incidence_angle_rad must be in (0, π/2).")

    arr = array.astype(np.float32)
    sigma0 = (arr ** 2) / calibration_factor * np.sin(incidence_angle_rad)
    return sigma0


def despeckle(array: NDArray, window_size: int = 5) -> NDArray:
    """Lee-filter approximation using a uniform mean filter.

    Parameters
    ----------
    array:
        SAR backscatter array (float32).
    window_size:
        Kernel size for the mean filter (must be odd, ≥ 3).
    """
    if window_size < 3 or window_size % 2 == 0:
        raise SARCalibrationError("window_size must be an odd integer ≥ 3.")

    arr = array.astype(np.float32)
    mean = uniform_filter(arr, size=window_size)
    mean_sq = uniform_filter(arr ** 2, size=window_size)
    variance = mean_sq - mean ** 2
    noise_var = np.mean(variance)
    weight = variance / (variance + noise_var + 1e-10)
    return mean + weight * (arr - mean)
