export function getPublicAssetUrl(assetPath: string): string {
  const normalizedPath = assetPath.replace(/^\/+/, '');
  return `${import.meta.env.BASE_URL}${normalizedPath}`;
}

const BRAND_ASSET_VERSION = '20260408-2';

export const brandLogoUrl = `${getPublicAssetUrl('logo.svg')}?v=${BRAND_ASSET_VERSION}`;
export const brandFaviconUrl = `${getPublicAssetUrl('favicon.svg')}?v=${BRAND_ASSET_VERSION}`;
