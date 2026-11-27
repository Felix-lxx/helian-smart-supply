"""Fixed-provider tile proxy. Provider credentials never appear in client URLs."""
from django.conf import settings
from django.http import HttpResponse,JsonResponse
from django.core.cache import cache
from django.urls import path
from django.views.decorators.http import require_GET
from rest_framework.decorators import api_view,permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
import requests
from threading import BoundedSemaphore
tile_slots=BoundedSemaphore(6)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def config(request):
    return Response({'enabled':bool(settings.TIANDITU_API_KEY),'provider':'天地图',
        'tile_url':request.build_absolute_uri('/api/workspace/maps/tiles/')+'{layer}/{z}/{x}/{y}/',
        'attribution':'底图 © 天地图','coordinate_system':'CGCS2000/WGS84 地理坐标 · Web Mercator 显示',
        'note':'业务坐标必须与底图一致；示例行政区域坐标不代表精确经营位置。'})


@require_GET
def tile(request,layer,z,x,y):
    if not settings.TIANDITU_API_KEY:return JsonResponse({'detail':'地图服务未配置'},status=503)
    if layer not in ['vec','cva'] or not 3<=z<=18 or not (0<=x<2**z and 0<=y<2**z):
        return JsonResponse({'detail':'地图请求范围无效'},status=400)
    if cache.get('tianditu:unavailable'):
        return JsonResponse({'detail':'在线地图暂不可用，请使用行政区概览'},status=503)
    key=f'tianditu:{layer}:{z}:{x}:{y}'
    cached=cache.get(key)
    if cached:
        content,kind=cached
    else:
        try:
            if not tile_slots.acquire(timeout=.1):
                return JsonResponse({'detail':'地图正在加载，可使用行政区概览'},status=503)
            try:
                response=requests.get(f'https://t0.tianditu.gov.cn/{layer}_w/wmts',params={
                    'SERVICE':'WMTS','REQUEST':'GetTile','VERSION':'1.0.0','LAYER':layer,
                    'STYLE':'default','TILEMATRIXSET':'w','FORMAT':'tiles','TILEMATRIX':z,
                    'TILEROW':y,'TILECOL':x,'tk':settings.TIANDITU_API_KEY},
                    headers={'User-Agent':'Mozilla/5.0','Referer':settings.MAP_CLIENT_ORIGIN},timeout=12)
            finally:
                tile_slots.release()
            content=response.content
            if response.status_code!=200 or len(content)>2*1024*1024:
                cache.set('tianditu:unavailable',True,timeout=30)
                return JsonResponse({'detail':'天地图服务暂不可用，请使用离线产地概览'},status=502)
            if content.startswith(b'\x89PNG\r\n\x1a\n'):kind='image/png'
            elif content.startswith(b'\xff\xd8'):kind='image/jpeg'
            else:
                cache.set('tianditu:unavailable',True,timeout=30)
                return JsonResponse({'detail':'地图服务未返回有效瓦片，请检查服务授权'},status=502)
            cache.set(key,(content,kind),timeout=86400)
        except requests.RequestException:
            cache.set('tianditu:unavailable',True,timeout=30)
            # Exceptions can contain the upstream query URL: never print them with credentials.
            return JsonResponse({'detail':'地图连接暂不可用，可切换离线产地概览'},status=502)
    result=HttpResponse(content,content_type=kind)
    result['Cache-Control']='public, max-age=86400'
    result['X-Content-Type-Options']='nosniff'
    return result


urlpatterns=[path('maps/config/',config),path('maps/tiles/<str:layer>/<int:z>/<int:x>/<int:y>/',tile)]
