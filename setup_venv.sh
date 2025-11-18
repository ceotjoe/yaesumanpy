#!/bin/sh
set -e

VENV_DIR="${VENV_DIR:-.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [ ! -d "${VENV_DIR}" ]; then
    echo "Creating virtual environment in ${VENV_DIR}..."
    "${PYTHON_BIN}" -m venv "${VENV_DIR}"
    echo "Virtual environment created."
fi

TARGET_VENV="$(cd "${VENV_DIR}" && pwd)"

if [ -z "${VIRTUAL_ENV}" ]; then
    echo "Activate the virtual environment before installing dependencies:"
    echo "  . ${VENV_DIR}/bin/activate"
    echo "Then rerun this script to install the requirements."
    exit 0
fi

if [ "${VIRTUAL_ENV}" != "${TARGET_VENV}" ]; then
    echo "Another virtual environment is active (${VIRTUAL_ENV})."
    echo "Please deactivate it, activate ${TARGET_VENV}, and rerun this script."
    exit 1
fi

echo "Installing dependencies inside ${VIRTUAL_ENV}..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Environment ready."
