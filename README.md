# Bridge between XBMC and Upstart.

## Upstart events
    player
        environment variables:
            ACTION=PLAY
                XBMC started playing something or playback has resumed.
            ACTION=PAUSE
                The playback has been paused by the user.
            ACTION=STOP
                XBMC stopped playing something, either because the stream has ended or it was interrupted by the user.

            TYPE=AUDIO
                The "something" above is an audio stream.
            TYPE=MOVIE
                The "something" above is a movie.
            TYPE=NONE
                XXX this doesn't appear to be used and should probably be removed
            TYPE=TVSHOW
                The "something" above is a tv show (episode).

    library
        environment variables:
            ACTION=START
                The action referenced in "MODE" has started.
            ACTION=STOP
                The action referenced in "MODE" has ended.
            ACTION=UPDATED
                The library referenced in "TYPE" has been updated.  "MODE" is always "NONE" with this action.

            MODE=CLEAN
                A clean has started/ended for the library referenced in "TYPE".
            MODE=NONE
                Ignore, just look at "ACTION".  This is only used for the action "UPDATED".
            MODE=SCAN
                A scan has started/ended for the library referenced in "TYPE".

            TYPE=AUDIO
                The action is being performed on the audio library.
            TYPE=VIDEO
                The action is being performed on the video library.

    screensaver
        environment variables:
            ACTION=START
                The XBMC screensaver has been activated.
            ACTION=STOP
                The XBMC screensaver has been deactivated.

In addition to these, it'll also emit the event `xbmcplevel` (as in "XBMC priority level").

An Upstart script interprets the value specified in `LEVEL` and changes the process priority dynamically.

Please note that the event `library ACTION=UPDATED MODE=NONE` is not considered an action on a library here.

    xbmcplevel
        environment variables:
            LEVEL=1
                Lowest priority.  The screensaver is active, it's not playing anything and no actions are being performed on the libraries.
            LEVEL=2
                Low priority.  The screensaver is active.  It's also either playing something or an action is being performed on any library.
            LEVEL=3
                Normal priority.  The screensaver is inactive, it's not playing anything and no actions are being performed on the libraries.
            LEVEL=4
                High priority.  The screensaver is inactive.  It's also either playing something or an action is being performed on any library.
            LEVEL=5
                Highest priority.  The screensaver is inactive, it's playing something and an action is being performed on any library.

            PREVLEVEL
                Valid values: 1, 2, 3, 4, 5.
                Previous priority level.  See "LEVEL" above for a description of each level.
