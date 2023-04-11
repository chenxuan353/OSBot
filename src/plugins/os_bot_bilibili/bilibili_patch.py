import io
import httpx
from PIL import Image
from bilibili_api import Credential, Picture
from bilibili_api.login_func import API

# Picture patch


def __set_picture_meta_from_bytes(self: Picture, imgtype: str):
    img = Image.open(io.BytesIO(self.content))
    self.size = img.size
    self.height = img.height
    self.width = img.width
    self.imageType = self.imageType = img.format.lower() if img.format else imgtype


async def upload_file(self: Picture, credential: Credential) -> "Picture":
    """
    上传图片至 B 站。

    Args:
        credential (Credential): 凭据类。

    Returns:
        Picture: `self`
    """
    from bilibili_api.dynamic import upload_image

    res = await upload_image(self, credential)
    self.height = res["image_height"]
    self.width = res["image_width"]
    self.url = res["image_url"]
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            self.url,
            cookies=credential.get_cookies(),
        )
        self.content = resp.read()
    return self


Picture.upload_file = upload_file
Picture.__set_picture_meta_from_bytes = __set_picture_meta_from_bytes
