export function getPublicAssetUrl(assetPath: string): string {
  const normalizedPath = assetPath.replace(/^\/+/, '');
  return `${import.meta.env.BASE_URL}${normalizedPath}`;
}

const BRAND_ASSET_VERSION = '20260506-uploaded-logo-3';

export const brandLogoUrl = `${getPublicAssetUrl('logo.png')}?v=${BRAND_ASSET_VERSION}`;
export const brandFaviconUrl = `${getPublicAssetUrl('favicon.png')}?v=${BRAND_ASSET_VERSION}`;
export const brandWordmarkUrl = `${getPublicAssetUrl('wordmark.png')}?v=${BRAND_ASSET_VERSION}`;
export const brandFullLogoUrl = `${getPublicAssetUrl('full-logo.png')}?v=${BRAND_ASSET_VERSION}`;
export const brandFullLogoLoginWhiteUrl = `${getPublicAssetUrl('full-logo-login-white.png')}?v=${BRAND_ASSET_VERSION}`;
