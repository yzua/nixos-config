# Manage Vesktop and a curated set of Vencord plugins without rebuilding the cached package.

{ nixcord, ... }:

{
  imports = [ nixcord.homeModules.nixcord ];

  programs.nixcord = {
    enable = true;
    discord.enable = false;
    vesktop = {
      enable = true;
      # Nixcord otherwise switches on a package override that builds Vesktop locally.
      useSystemVencord = false;
    };

    config = {
      # Disable Vencord's in-app updater; Vesktop may still fetch its mod at runtime.
      autoUpdate = false;
      plugins = {
        # Readable messages and replies that do not ping by default.
        betterGifAltText.enable = true;
        characterCounter.enable = true;
        noReplyMention = {
          enable = true;
          # The upstream defaults contain example user/role IDs, not preferences.
          userList = "";
          roleList = "";
        };

        # Less friction navigating servers, settings, and conversations.
        betterFolders.enable = true;
        betterSettings.enable = true;
        keepCurrentChannel.enable = true;
        fullSearchContext.enable = true;
        readAllNotificationsButton.enable = true;
        quickReply.enable = true;
        moreQuickReactions.enable = true;
        sendTimestamps = {
          enable = true;
          # Keep its timestamp button, but do not rewrite typed messages.
          replaceMessageContents = false;
        };
        copyFileContents.enable = true;

        # Better media without external themes or an oversized image-in-chat load.
        imageZoom = {
          enable = true;
          # The managed settings file cannot persist tweaks made inside Vesktop.
          saveZoomValues = false;
        };
        fixImagesQuality.enable = true;
        biggerStreamPreview.enable = true;

        # Useful context and fewer accidental voice joins.
        memberCount.enable = true;
        permissionsViewer.enable = true;
        voiceChatDoubleClick.enable = true;
      };
    };
  };
}
