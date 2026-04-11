from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)
response = client.get("/api/products")
assert response.status_code == 200
data = response.json()
print(f"Total products: {data['pagination']['total']}")
if data['products']:
    first_product = data['products'][0]
    print(f"Product 1 keys: {first_product.keys()}")
    print(f"Has images? {'images' in first_product and first_product['images'] is not None}")
    print(f"Has ai_metadata? {'ai_metadata' in first_product and first_product['ai_metadata'] is not None}")
