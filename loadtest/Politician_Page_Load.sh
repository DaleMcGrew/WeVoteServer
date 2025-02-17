DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
locust -f $DIR/PoliticianPageLoad.py --host=https://api.wevoteusa.org  --users 2000 --spawn-rate 2000 --run-time 10m