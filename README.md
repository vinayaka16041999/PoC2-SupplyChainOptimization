# Supply Chain Optimization PoC

This project is a Proof of Concept (PoC) for a Supply Chain Optimization system. It includes real-time data generation, analytics, and visualization components to monitor and optimize supply chain operations.

## Project Structure

The project is organized into the following components:

1. **Data Generator**: Simulates real-time supply chain data.
2. **Analytics Engine**: Processes the data, detects anomalies, and generates forecasts.
3. **Frontend**: Displays real-time health status and alerts.
4. **Query Frontend**: Allows querying historical data.
5. **Redis**: Serves as the message broker and data store.

## Components

### Data Generator

- **Directory**: `data_generator`
- **Description**: Generates simulated supply chain data and publishes it to Redis channels.
- **Main File**: `generator.py`
- **Dockerfile**: `data_generator/Dockerfile`

### Analytics Engine

- **Directory**: `analytics_engine`
- **Description**: Processes incoming data, detects anomalies, and generates forecasts.
- **Main File**: `analytics.py`
- **Dockerfile**: `analytics_engine/Dockerfile`

### Frontend

- **Directory**: `frontend`
- **Description**: Displays real-time health status and alerts using Flask and Socket.IO.
- **Main File**: `app.py`
- **Dockerfile**: `frontend/Dockerfile`

### Query Frontend

- **Directory**: `query_frontend`
- **Description**: Provides an interface to query historical supply chain data.
- **Main File**: `app.py`
- **Dockerfile**: `query_frontend/Dockerfile`

### Redis

- **Image**: `redis:latest`
- **Description**: Acts as the message broker and data store for the system.

## Setup and Running

### Prerequisites

- Docker
- Docker Compose

### Steps

1. Clone the repository:
    ```sh
    git clone <repository-url>
    cd PoC2-SupplyChainOptimization
    ```

2. Build and start the services using Docker Compose:
    ```sh
    docker-compose up --build
    ```

3. Access the frontends:
    - Real-Time Health Status: [http://localhost:5000](http://localhost:5000)
    - Query Frontend: [http://localhost:5002](http://localhost:5002)

## Configuration

- **Docker Compose File**: `docker-compose.yml`
- **Environment Variables**: Configure Redis host and port if needed.

## Dependencies

- Flask
- Redis
- Flask-SocketIO
- NumPy
- Pandas
- Scikit-learn
- Statsmodels

## License

This project is licensed under the MIT License.

## Acknowledgements

- Flask
- Redis
- Docker
- Chart.js

For more details, refer to the individual component directories and their respective documentation.
