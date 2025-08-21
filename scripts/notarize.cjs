const { notarize } = require('@electron/notarize');

module.exports = async function notarizing(context) {
  const { electronPlatformName, appOutDir } = context;
  if (electronPlatformName !== 'darwin') {
    return;
  }

  const appName = context.packager.appInfo.productFilename;

  if (!process.env.APPLE_ID || !process.env.APPLE_ID_PASS) {
    console.log('Skipping notarization - APPLE_ID and APPLE_ID_PASS not provided');
    return;
  }

  return await notarize({
    appBundleId: 'com.efsoft.omr',
    appPath: `${appOutDir}/${appName}.app`,
    appleId: process.env.APPLE_ID,
    appleIdPassword: process.env.APPLE_ID_PASS,
  });
};