# monzo-script

**monzo-script** is a Python-based utility designed to interact with the Monzo banking API. This tool facilitates automation and scripting tasks related to Monzo accounts, enabling users to programmatically manage their finances.

## Features

- **API Integration**: Seamlessly connect to the Monzo API to retrieve account information, transactions, and more.
- **Automation**: Automate routine banking tasks such as transaction categorization, balance monitoring, and financial reporting.
- **Custom Scripting**: Write custom scripts to tailor the functionality to your specific needs.

## Requirements

- Python 3.11 or higher
- Monzo API access token

## Installation

Clone the repository:

```bash
git clone https://github.com/rippleFCL/monzo-script.git
cd monzo-script
```

Install dependencies using Poetry:

```bash
poetry install
```

Alternatively, you can install dependencies manually:

```bash
pip install -r requirements.txt
```

## Usage

To use the script, ensure you have your Monzo API access token. Then, run the script with your desired parameters:

```bash
how-run.sh --weh
```


## Testing

To run the test suite:

```bash
pytest
```

Ensure that you have set up any necessary environment variables or configuration files before running tests.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.
