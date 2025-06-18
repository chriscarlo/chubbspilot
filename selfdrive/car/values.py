from typing import get_args
from selfdrive.car.body.values import CAR as BODY
from selfdrive.car.chrysler.values import CAR as CHRYSLER
from selfdrive.car.ford.values import CAR as FORD
from selfdrive.car.gm.values import CAR as GM
from selfdrive.car.honda.values import CAR as HONDA
from selfdrive.car.hyundai.values import CAR as HYUNDAI
from selfdrive.car.mazda.values import CAR as MAZDA
from selfdrive.car.mock.values import CAR as MOCK
from selfdrive.car.nissan.values import CAR as NISSAN
from selfdrive.car.subaru.values import CAR as SUBARU
from selfdrive.car.tesla.values import CAR as TESLA
from selfdrive.car.toyota.values import CAR as TOYOTA
from selfdrive.car.volkswagen.values import CAR as VOLKSWAGEN

Platform = BODY | CHRYSLER | FORD | GM | HONDA | HYUNDAI | MAZDA | MOCK | NISSAN | SUBARU | TESLA | TOYOTA | VOLKSWAGEN
BRANDS = get_args(Platform)

PLATFORMS: dict[str, Platform] = {str(platform): platform for brand in BRANDS for platform in brand}
