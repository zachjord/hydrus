import HydrusConstants as HC
import HydrusAudioHandling
import ClientDownloading
import HydrusExceptions
import HydrusPaths
import HydrusSerialisable
import HydrusThreading
import ClientConstants as CC
import ClientData
import ClientDefaults
import ClientCaches
import ClientFiles
import ClientGUIACDropdown
import ClientGUICanvas
import ClientGUICollapsible
import ClientGUICommon
import ClientGUIControls
import ClientGUIDialogs
import ClientGUIListBoxes
import ClientGUIMedia
import ClientGUIMenus
import ClientGUIScrolledPanelsEdit
import ClientGUISeedCache
import ClientGUITopLevelWindows
import ClientImporting
import ClientMedia
import ClientRendering
import ClientThreading
import json
import multipart
import os
import threading
import time
import traceback
import urlparse
import webbrowser
import wx
import wx.lib.scrolledpanel
import HydrusData
import ClientSearch
import HydrusGlobals as HG

CAPTCHA_FETCH_EVENT_TYPE = wx.NewEventType()
CAPTCHA_FETCH_EVENT = wx.PyEventBinder( CAPTCHA_FETCH_EVENT_TYPE )

ID_TIMER_CAPTCHA = wx.NewId()
ID_TIMER_DUMP = wx.NewId()
ID_TIMER_UPDATE = wx.NewId()
ID_TIMER_IMPORT_UPDATE = wx.NewId()

MANAGEMENT_TYPE_DUMPER = 0
MANAGEMENT_TYPE_IMPORT_GALLERY = 1
MANAGEMENT_TYPE_IMPORT_PAGE_OF_IMAGES = 2
MANAGEMENT_TYPE_IMPORT_HDD = 3
MANAGEMENT_TYPE_IMPORT_THREAD_WATCHER = 4
MANAGEMENT_TYPE_PETITIONS = 5
MANAGEMENT_TYPE_QUERY = 6
MANAGEMENT_TYPE_IMPORT_URLS = 7
MANAGEMENT_TYPE_DUPLICATE_FILTER = 8

management_panel_types_to_classes = {}

def CreateManagementController( page_name, management_type, file_service_key = None ):
    
    if file_service_key is None:
        
        file_service_key = CC.COMBINED_LOCAL_FILE_SERVICE_KEY
        
    
    new_options = HG.client_controller.GetNewOptions()
    
    management_controller = ManagementController( page_name )
    
    management_controller.SetType( management_type )
    management_controller.SetKey( 'file_service', file_service_key )
    management_controller.SetVariable( 'media_sort', new_options.GetDefaultSort() )
    
    return management_controller
    
def CreateManagementControllerDuplicateFilter():
    
    management_controller = CreateManagementController( 'duplicates', MANAGEMENT_TYPE_DUPLICATE_FILTER )
    
    management_controller.SetKey( 'duplicate_filter_file_domain', CC.LOCAL_FILE_SERVICE_KEY )
    
    return management_controller
    
def CreateManagementControllerImportGallery( gallery_identifier ):
    
    page_name = gallery_identifier.ToString()
    
    management_controller = CreateManagementController( page_name, MANAGEMENT_TYPE_IMPORT_GALLERY )
    
    gallery_import = ClientImporting.GalleryImport( gallery_identifier = gallery_identifier )
    
    management_controller.SetVariable( 'gallery_import', gallery_import )
    
    return management_controller
    
def CreateManagementControllerImportPageOfImages():
    
    management_controller = CreateManagementController( 'page download', MANAGEMENT_TYPE_IMPORT_PAGE_OF_IMAGES )
    
    page_of_images_import = ClientImporting.PageOfImagesImport()
    
    management_controller.SetVariable( 'page_of_images_import', page_of_images_import )
    
    return management_controller
    
def CreateManagementControllerImportHDD( paths, import_file_options, paths_to_tags, delete_after_success ):
    
    management_controller = CreateManagementController( 'import', MANAGEMENT_TYPE_IMPORT_HDD )
    
    hdd_import = ClientImporting.HDDImport( paths = paths, import_file_options = import_file_options, paths_to_tags = paths_to_tags, delete_after_success = delete_after_success )
    
    management_controller.SetVariable( 'hdd_import', hdd_import )
    
    return management_controller
    
def CreateManagementControllerImportThreadWatcher( thread_url = None ):
    
    management_controller = CreateManagementController( 'thread watcher', MANAGEMENT_TYPE_IMPORT_THREAD_WATCHER )
    
    thread_watcher_import = ClientImporting.ThreadWatcherImport()
    
    management_controller.SetVariable( 'thread_watcher_import', thread_watcher_import )
    
    if thread_url is not None:
        
        try:
            
            ( thread_url, host, board, thread_id ) = ClientDownloading.ParseImageboardThreadURL( thread_url )
            
        except Exception as e:
            
            HydrusData.ShowException( e )
            
            return
            
        
        thread_watcher_import.SetThreadURL( thread_url )
        
    
    return management_controller
    
def CreateManagementControllerImportURLs():
    
    management_controller = CreateManagementController( 'url import', MANAGEMENT_TYPE_IMPORT_URLS )
    
    urls_import = ClientImporting.URLsImport()
    
    management_controller.SetVariable( 'urls_import', urls_import )
    
    return management_controller
    
def CreateManagementControllerPetitions( petition_service_key ):
    
    petition_service = HG.client_controller.services_manager.GetService( petition_service_key )
    
    page_name = petition_service.GetName() + ' petitions'
    
    petition_service_type = petition_service.GetServiceType()
    
    if petition_service_type in HC.LOCAL_FILE_SERVICES or petition_service_type == HC.FILE_REPOSITORY:
        
        file_service_key = petition_service_key
        
    else:
        
        file_service_key = CC.COMBINED_FILE_SERVICE_KEY
        
    
    management_controller = CreateManagementController( page_name, MANAGEMENT_TYPE_PETITIONS, file_service_key = file_service_key )
    
    management_controller.SetKey( 'petition_service', petition_service_key )
    
    return management_controller
    
def CreateManagementControllerQuery( page_name, file_service_key, file_search_context, search_enabled ):
    
    management_controller = CreateManagementController( page_name, MANAGEMENT_TYPE_QUERY, file_service_key = file_service_key )
    
    management_controller.SetVariable( 'file_search_context', file_search_context )
    management_controller.SetVariable( 'search_enabled', search_enabled )
    management_controller.SetVariable( 'synchronised', True )
    
    return management_controller
    
def CreateManagementPanel( parent, page, controller, management_controller ):
    
    management_type = management_controller.GetType()
    
    management_class = management_panel_types_to_classes[ management_type ]
    
    management_panel = management_class( parent, page, controller, management_controller )
    
    return management_panel
    
def GenerateDumpMultipartFormDataCTAndBody( fields ):
    
    m = multipart.Multipart()
    
    for ( name, field_type, value ) in fields:
        
        if field_type in ( CC.FIELD_TEXT, CC.FIELD_COMMENT, CC.FIELD_PASSWORD, CC.FIELD_VERIFICATION_RECAPTCHA, CC.FIELD_THREAD_ID ):
            
            m.field( name, HydrusData.ToByteString( value ) )
            
        elif field_type == CC.FIELD_CHECKBOX:
            
            if value:
                
                # spoiler/on -> name : spoiler, value : on
                # we don't say true/false for checkboxes
                
                ( name, value ) = name.split( '/', 1 )
                
                m.field( name, value )
                
            
        elif field_type == CC.FIELD_FILE:
            
            ( hash, mime, file ) = value
            
            m.file( name, hash.encode( 'hex' ) + HC.mime_ext_lookup[ mime ], file, { 'Content-Type' : HC.mime_string_lookup[ mime ] } )
            
        
    
    return m.get()
    
'''class CaptchaControl( wx.Panel ):
    
    def __init__( self, parent, captcha_type, default ):
        
        wx.Panel.__init__( self, parent )
        
        self._captcha_key = default
        
        self._captcha_challenge = None
        self._captcha_runs_out = 0
        self._bitmap = wx.EmptyBitmap( 20, 20, 24 )
        
        self._timer = wx.Timer( self, ID_TIMER_CAPTCHA )
        self.Bind( wx.EVT_TIMER, self.TIMEREvent, id = ID_TIMER_CAPTCHA )
        
        self._captcha_box_panel = ClientGUICommon.StaticBox( self, 'recaptcha' )
        
        self._captcha_panel = ClientGUICommon.BufferedWindow( self._captcha_box_panel, size = ( 300, 57 ) )
        
        self._refresh_button = wx.Button( self._captcha_box_panel, label = '' )
        self._refresh_button.Bind( wx.EVT_BUTTON, self.EventRefreshCaptcha )
        self._refresh_button.Disable()
        
        self._captcha_time_left = ClientGUICommon.BetterStaticText( self._captcha_box_panel )
        
        self._captcha_entry = wx.TextCtrl( self._captcha_box_panel, style = wx.TE_PROCESS_ENTER )
        self._captcha_entry.Bind( wx.EVT_KEY_DOWN, self.EventKeyDown )
        
        self._ready_button = wx.Button( self._captcha_box_panel, label = '' )
        self._ready_button.Bind( wx.EVT_BUTTON, self.EventReady )
        
        sub_vbox = wx.BoxSizer( wx.VERTICAL )
        
        sub_vbox.AddF( self._refresh_button, CC.FLAGS_EXPAND_BOTH_WAYS )
        sub_vbox.AddF( self._captcha_time_left, CC.FLAGS_SMALL_INDENT )
        
        hbox = wx.BoxSizer( wx.HORIZONTAL )
        
        hbox.AddF( self._captcha_panel, CC.FLAGS_NONE )
        hbox.AddF( sub_vbox, CC.FLAGS_EXPAND_SIZER_BOTH_WAYS )
        
        hbox2 = wx.BoxSizer( wx.HORIZONTAL )
        
        hbox2.AddF( self._captcha_entry, CC.FLAGS_EXPAND_BOTH_WAYS )
        hbox2.AddF( self._ready_button, CC.FLAGS_VCENTER )
        
        self._captcha_box_panel.AddF( hbox, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        self._captcha_box_panel.AddF( hbox2, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        
        vbox = wx.BoxSizer( wx.VERTICAL )
        
        vbox.AddF( self._captcha_box_panel, CC.FLAGS_EXPAND_BOTH_WAYS )
        
        self.SetSizer( vbox )
        
        self.Disable()
        
    
    def _DrawEntry( self, entry = None ):
        
        if entry is None:
            
            self._captcha_entry.SetValue( '' )
            self._captcha_entry.Disable()
            
        else: self._captcha_entry.SetValue( entry )
        
    
    def _DrawMain( self, dc ):
        
        if self._captcha_challenge is None:
            
            dc.Clear()
            
            self._refresh_button.SetLabelText( '' )
            self._refresh_button.Disable()
            
            self._captcha_time_left.SetLabelText( '' )
            
        elif self._captcha_challenge == '':
            
            dc.Clear()
            
            event = wx.NotifyEvent( CAPTCHA_FETCH_EVENT_TYPE )
            
            self.ProcessEvent( event )
            
            if event.IsAllowed():
                
                self._refresh_button.SetLabelText( 'get captcha' )
                self._refresh_button.Enable()
                
            else:
                
                self._refresh_button.SetLabelText( 'not yet' )
                self._refresh_button.Disable()
                
            
            self._captcha_time_left.SetLabelText( '' )
            
        else:
            
            wx_bmp = self._bitmap.GetWxBitmap()
            
            dc.DrawBitmap( wx_bmp, 0, 0 )
            
            wx_bmp.Destroy()
            
            self._refresh_button.SetLabelText( 'get new captcha' )
            self._refresh_button.Enable()
            
            self._captcha_time_left.SetLabelText( HydrusData.ConvertTimestampToPrettyExpires( self._captcha_runs_out ) )
            
        
        del dc
        
    
    def _DrawReady( self, ready = None ):
        
        if ready is None:
            
            self._ready_button.SetLabelText( '' )
            self._ready_button.Disable()
            
        else:
            
            if ready:
                
                self._captcha_entry.Disable()
                self._ready_button.SetLabelText( 'edit' )
                
            else:
                
                self._captcha_entry.Enable()
                self._ready_button.SetLabelText( 'ready' )
                
            
            self._ready_button.Enable()
            
        
    
    def Disable( self ):
        
        self._captcha_challenge = None
        self._captcha_runs_out = 0
        self._bitmap = wx.EmptyBitmap( 20, 20, 24 )
        
        self._DrawMain()
        self._DrawEntry()
        self._DrawReady()
        
        self._timer.Stop()
        
    
    def Enable( self ):
        
        self._captcha_challenge = ''
        self._captcha_runs_out = 0
        self._bitmap = wx.EmptyBitmap( 20, 20, 24 )
        
        self._DrawMain()
        self._DrawEntry()
        self._DrawReady()
        
        self._timer.Start( 1000, wx.TIMER_CONTINUOUS )
        
    
    def EnableWithValues( self, challenge, bitmap, captcha_runs_out, entry, ready ):
        
        if HydrusData.TimeHasPassed( captcha_runs_out ): self.Enable()
        else:
            
            self._captcha_challenge = challenge
            self._captcha_runs_out = captcha_runs_out
            self._bitmap = bitmap
            
            self._DrawMain()
            self._DrawEntry( entry )
            self._DrawReady( ready )
            
            self._timer.Start( 1000, wx.TIMER_CONTINUOUS )
            
        
    
    def EventKeyDown( self, event ):
        
        ( modifier, key ) = ClientData.ConvertKeyEventToSimpleTuple( event )
        
        if key in ( wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER ): self.EventReady( None )
        else: event.Skip()
        
    
    def EventReady( self, event ): self._DrawReady( not self._ready_button.GetLabelText() == 'edit' )
    
    def EventRefreshCaptcha( self, event ):
        
        javascript_string = self._controller.DoHTTP( HC.GET, 'https://www.google.com/recaptcha/api/challenge?k=' + self._captcha_key )
        
        ( trash, rest ) = javascript_string.split( 'challenge : \'', 1 )
        
        ( self._captcha_challenge, trash ) = rest.split( '\'', 1 )
        
        jpeg = self._controller.DoHTTP( HC.GET, 'https://www.google.com/recaptcha/api/image?c=' + self._captcha_challenge )
        
        ( os_file_handle, temp_path ) = HydrusPaths.GetTempPath()
        
        try:
            
            with open( temp_path, 'wb' ) as f: f.write( jpeg )
            
            self._bitmap = ClientRendering.GenerateHydrusBitmap( temp_path, HC.IMAGE_JPEG )
            
        finally:
            
            HydrusPaths.CleanUpTempPath( os_file_handle, temp_path )
            
        
        self._captcha_runs_out = HydrusData.GetNow() + 5 * 60 - 15
        
        self._DrawMain()
        self._DrawEntry( '' )
        self._DrawReady( False )
        
        self._timer.Start( 1000, wx.TIMER_CONTINUOUS )
        
    
    # change this to hold (current challenge, bmp, timestamp it runs out, value, whethere ready to post)
    def GetValues( self ): return ( self._captcha_challenge, self._bitmap, self._captcha_runs_out, self._captcha_entry.GetValue(), self._ready_button.GetLabelText() == 'edit' )
    
    def TIMEREvent( self, event ):
        
        try:
            
            if HydrusData.TimeHasPassed( self._captcha_runs_out ):
                
                self.Enable()
                
            else:
                
                self._DrawMain()
                
            
        except wx.PyDeadObjectError:
            
            self._timer.Stop()
            
        except:
            
            self._timer.Stop()
            
            raise
            
        
    '''

'''class Comment( wx.Panel ):
    
    def __init__( self, parent ):
        
        wx.Panel.__init__( self, parent )
        
        self._initial_comment = ''
        
        self._comment_panel = ClientGUICommon.StaticBox( self, 'comment' )
        
        self._comment = ClientGUICommon.SaneMultilineTextCtrl( self._comment_panel, style = wx.TE_READONLY )
        
        self._comment_append = ClientGUICommon.SaneMultilineTextCtrl( self._comment_panel, style = wx.TE_PROCESS_ENTER )
        self._comment_append.Bind( wx.EVT_KEY_UP, self.EventKeyDown )
        
        self._comment_panel.AddF( self._comment, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._comment_panel.AddF( self._comment_append, CC.FLAGS_EXPAND_PERPENDICULAR )
        
        vbox = wx.BoxSizer( wx.VERTICAL )
        
        vbox.AddF( self._comment_panel, CC.FLAGS_EXPAND_BOTH_WAYS )
        
        self.SetSizer( vbox )
        
    
    def _SetComment( self ):
        
        append = self._comment_append.GetValue()
        
        if self._initial_comment != '' and append != '': comment = self._initial_comment + os.linesep * 2 + append
        else: comment = self._initial_comment + append
        
        self._comment.SetValue( comment )
        
    
    def Disable( self ):
        
        self._initial_comment = ''
        
        self._comment_append.SetValue( '' )
        self._comment_append.Disable()
        
        self._SetComment()
        
    
    def EnableWithValues( self, initial, append ):
        
        self._initial_comment = initial
        
        self._comment_append.SetValue( append )
        self._comment_append.Enable()
        
        self._SetComment()
        
    
    def GetValues( self ): return ( self._initial_comment, self._comment_append.GetValue() )
    
    def EventKeyDown( self, event ):
        
        self._SetComment()
        
        event.Skip()
        
    '''
class ManagementController( HydrusSerialisable.SerialisableBase ):
    
    SERIALISABLE_TYPE = HydrusSerialisable.SERIALISABLE_TYPE_MANAGEMENT_CONTROLLER
    SERIALISABLE_VERSION = 3
    
    def __init__( self, page_name = 'page' ):
        
        HydrusSerialisable.SerialisableBase.__init__( self )
        
        self._page_name = page_name
        
        self._management_type = None
        
        self._keys = {}
        self._simples = {}
        self._serialisables = {}
        
    
    def _GetSerialisableInfo( self ):
        
        serialisable_keys = { name : value.encode( 'hex' ) for ( name, value ) in self._keys.items() }
        
        serialisable_simples = dict( self._simples )
        
        serialisable_serialisables = { name : value.GetSerialisableTuple() for ( name, value ) in self._serialisables.items() }
        
        return ( self._page_name, self._management_type, serialisable_keys, serialisable_simples, serialisable_serialisables )
        
    
    def _InitialiseDefaults( self ):
        
        self._serialisables[ 'media_sort' ] = ClientMedia.MediaSort( ( 'system', CC.SORT_FILES_BY_FILESIZE ), CC.SORT_ASC )
        
        if self._management_type == MANAGEMENT_TYPE_DUPLICATE_FILTER:
            
            self._keys[ 'duplicate_filter_file_domain' ] = CC.LOCAL_FILE_SERVICE_KEY
            
        
    
    def _InitialiseFromSerialisableInfo( self, serialisable_info ):
        
        ( self._page_name, self._management_type, serialisable_keys, serialisable_simples, serialisables ) = serialisable_info
        
        self._InitialiseDefaults()
        
        self._keys.update( { name : key.decode( 'hex' ) for ( name, key ) in serialisable_keys.items() } )
        
        if 'file_service' in self._keys:
            
            if not HG.client_controller.services_manager.ServiceExists( self._keys[ 'file_service' ] ):
                
                self._keys[ 'file_service' ] = CC.COMBINED_LOCAL_FILE_SERVICE_KEY
                
            
        
        self._simples.update( dict( serialisable_simples ) )
        
        self._serialisables.update( { name : HydrusSerialisable.CreateFromSerialisableTuple( value ) for ( name, value ) in serialisables.items() } )
        
    
    def _UpdateSerialisableInfo( self, version, old_serialisable_info ):
        
        if version == 1:
            
            ( management_type, serialisable_keys, serialisable_simples, serialisable_serialisables ) = old_serialisable_info
            
            if management_type == MANAGEMENT_TYPE_IMPORT_HDD:
                
                advanced_import_options = serialisable_simples[ 'advanced_import_options' ]
                paths_info = serialisable_simples[ 'paths_info' ]
                paths_to_tags = serialisable_simples[ 'paths_to_tags' ]
                delete_after_success = serialisable_simples[ 'delete_after_success' ]
                
                paths = [ path_info for ( path_type, path_info ) in paths_info if path_type != 'zip' ]
                
                automatic_archive = advanced_import_options[ 'automatic_archive' ]
                exclude_deleted = advanced_import_options[ 'exclude_deleted' ]
                min_size = advanced_import_options[ 'min_size' ]
                min_resolution = advanced_import_options[ 'min_resolution' ]
                
                import_file_options = ClientData.ImportFileOptions( automatic_archive = automatic_archive, exclude_deleted = exclude_deleted, min_size = min_size, min_resolution = min_resolution )
                
                paths_to_tags = { path : { service_key.decode( 'hex' ) : tags for ( service_key, tags ) in service_keys_to_tags } for ( path, service_keys_to_tags ) in paths_to_tags.items() }
                
                hdd_import = ClientImporting.HDDImport( paths = paths, import_file_options = import_file_options, paths_to_tags = paths_to_tags, delete_after_success = delete_after_success )
                
                serialisable_serialisables[ 'hdd_import' ] = hdd_import.GetSerialisableTuple()
                
                del serialisable_serialisables[ 'advanced_import_options' ]
                del serialisable_serialisables[ 'paths_info' ]
                del serialisable_serialisables[ 'paths_to_tags' ]
                del serialisable_serialisables[ 'delete_after_success' ]
                
            
            new_serialisable_info = ( management_type, serialisable_keys, serialisable_simples, serialisable_serialisables )
            
            return ( 2, new_serialisable_info )
            
        
        if version == 2:
            
            ( management_type, serialisable_keys, serialisable_simples, serialisable_serialisables ) = old_serialisable_info
            
            page_name = 'page'
            
            new_serialisable_info = ( page_name, management_type, serialisable_keys, serialisable_simples, serialisable_serialisables )
            
            return ( 3, new_serialisable_info )
            
        
    
    def GetKey( self, name ):
        
        return self._keys[ name ]
        
    
    def GetPageName( self ):
        
        return self._page_name
        
    
    def GetType( self ):
        
        return self._management_type
        
    
    def GetVariable( self, name ):
        
        if name in self._simples:
            
            return self._simples[ name ]
            
        else:
            
            return self._serialisables[ name ]
            
        
    
    def HasVariable( self, name ):
        
        return name in self._simples or name in self._serialisables
        
    
    def IsImporter( self ):
        
        return self._management_type in ( MANAGEMENT_TYPE_IMPORT_GALLERY, MANAGEMENT_TYPE_IMPORT_HDD, MANAGEMENT_TYPE_IMPORT_PAGE_OF_IMAGES, MANAGEMENT_TYPE_IMPORT_THREAD_WATCHER, MANAGEMENT_TYPE_IMPORT_URLS )
        
    
    def SetKey( self, name, key ):
        
        self._keys[ name ] = key
        
    
    def SetPageName( self, name ):
        
        self._page_name = name
        
    
    def SetType( self, management_type ):
        
        self._management_type = management_type
        
        self._InitialiseDefaults()
        
    
    def SetVariable( self, name, value ):
        
        if isinstance( value, HydrusSerialisable.SerialisableBase ):
            
            self._serialisables[ name ] = value
            
        else:
            
            self._simples[ name ] = value
            
        
    
HydrusSerialisable.SERIALISABLE_TYPES_TO_OBJECT_TYPES[ HydrusSerialisable.SERIALISABLE_TYPE_MANAGEMENT_CONTROLLER ] = ManagementController

class ManagementPanel( wx.lib.scrolledpanel.ScrolledPanel ):
    
    def __init__( self, parent, page, controller, management_controller ):
        
        wx.lib.scrolledpanel.ScrolledPanel.__init__( self, parent, style = wx.BORDER_NONE | wx.VSCROLL )
        
        self.SetupScrolling()
        
        self.SetBackgroundColour( wx.SystemSettings.GetColour( wx.SYS_COLOUR_FRAMEBK ) )
        
        self._controller = controller
        self._management_controller = management_controller
        
        self._page = page
        self._page_key = self._management_controller.GetKey( 'page' )
        
        self._sort_by = ClientGUICommon.ChoiceSort( self, management_controller = self._management_controller )
        
        self._collect_by = ClientGUICommon.CheckboxCollect( self, self._page_key )
        
        self._controller.sub( self, 'SetSearchFocus', 'set_search_focus' )
        
    
    def _MakeCurrentSelectionTagsBox( self, sizer ):
        
        tags_box = ClientGUICommon.StaticBoxSorterForListBoxTags( self, 'selection tags' )
        
        t = ClientGUIListBoxes.ListBoxTagsSelectionManagementPanel( tags_box, self._page_key )
        
        tags_box.SetTagsBox( t )
        
        sizer.AddF( tags_box, CC.FLAGS_EXPAND_BOTH_WAYS )
        
    
    def CleanBeforeDestroy( self ):
        
        pass
        
    
    def SetSearchFocus( self, page_key ):
        
        pass
        
    
    def Start( self ):
        
        pass
        
    
    def TestAbleToClose( self ):
        
        pass
        
    
class ManagementPanelDuplicateFilter( ManagementPanel ):
    
    def __init__( self, parent, page, controller, management_controller ):
        
        ManagementPanel.__init__( self, parent, page, controller, management_controller )
        
        self._job = None
        self._job_key = None
        self._in_break = False
        
        menu_items = []
        
        menu_items.append( ( 'normal', 'refresh', 'This panel does not update itself when files are added or deleted elsewhere in the client. Hitting this will refresh the numbers from the database.', self._RefreshAndUpdateStatus ) )
        menu_items.append( ( 'normal', 'reset potential duplicates', 'This will delete all the potential duplicate pairs found so far and reset their files\' search status.', self._ResetUnknown ) )
        menu_items.append( ( 'separator', 0, 0, 0 ) )
        
        check_manager = ClientGUICommon.CheckboxManagerOptions( 'maintain_similar_files_duplicate_pairs_during_idle' )
        
        menu_items.append( ( 'check', 'search for duplicate pairs at the current distance during normal db maintenance', 'Tell the client to find duplicate pairs in its normal db maintenance cycles, whether you have that set to idle or shutdown time.', check_manager ) )
        
        self._cog_button = ClientGUICommon.MenuBitmapButton( self, CC.GlobalBMPs.cog, menu_items )
        
        menu_items = []
        
        page_func = HydrusData.Call( webbrowser.open, 'file://' + HC.HELP_DIR + '/duplicates.html' )
        
        menu_items.append( ( 'normal', 'show some simpler help here', 'Throw up a message box with some simple help.', self._ShowSimpleHelp ) )
        menu_items.append( ( 'normal', 'open the html duplicates help', 'Open the help page for duplicates processing in your web browesr.', page_func ) )
        
        self._help_button = ClientGUICommon.MenuBitmapButton( self, CC.GlobalBMPs.help, menu_items )
        
        self._preparing_panel = ClientGUICommon.StaticBox( self, '1 - preparation' )
        
        # refresh button that just calls update
        
        self._num_phashes_to_regen = ClientGUICommon.BetterStaticText( self._preparing_panel )
        self._num_branches_to_regen = ClientGUICommon.BetterStaticText( self._preparing_panel )
        
        self._phashes_button = ClientGUICommon.BetterBitmapButton( self._preparing_panel, CC.GlobalBMPs.play, self._RegeneratePhashes )
        self._branches_button = ClientGUICommon.BetterBitmapButton( self._preparing_panel, CC.GlobalBMPs.play, self._RebalanceTree )
        
        #
        
        self._searching_panel = ClientGUICommon.StaticBox( self, '2 - discovery' )
        
        menu_items = []
        
        menu_items.append( ( 'normal', 'exact match', 'Search for exact matches.', HydrusData.Call( self._SetSearchDistance, HC.HAMMING_EXACT_MATCH ) ) )
        menu_items.append( ( 'normal', 'very similar', 'Search for very similar files.', HydrusData.Call( self._SetSearchDistance, HC.HAMMING_VERY_SIMILAR ) ) )
        menu_items.append( ( 'normal', 'similar', 'Search for similar files.', HydrusData.Call( self._SetSearchDistance, HC.HAMMING_SIMILAR ) ) )
        menu_items.append( ( 'normal', 'speculative', 'Search for files that are probably similar.', HydrusData.Call( self._SetSearchDistance, HC.HAMMING_SPECULATIVE ) ) )
        
        self._search_distance_button = ClientGUICommon.MenuButton( self._searching_panel, 'similarity', menu_items )
        
        self._search_distance_spinctrl = wx.SpinCtrl( self._searching_panel, min = 0, max = 64, size = ( 50, -1 ) )
        self._search_distance_spinctrl.Bind( wx.EVT_SPINCTRL, self.EventSearchDistanceChanged )
        
        self._num_searched = ClientGUICommon.TextAndGauge( self._searching_panel )
        
        self._search_button = ClientGUICommon.BetterBitmapButton( self._searching_panel, CC.GlobalBMPs.play, self._SearchForDuplicates )
        
        #
        
        self._filtering_panel = ClientGUICommon.StaticBox( self, '3 - processing' )
        
        self._file_domain_button = ClientGUICommon.BetterButton( self._filtering_panel, 'file domain', self._FileDomainButtonHit )
        self._num_unknown_duplicates = ClientGUICommon.BetterStaticText( self._filtering_panel )
        self._num_better_duplicates = ClientGUICommon.BetterStaticText( self._filtering_panel )
        self._num_better_duplicates.SetToolTipString( 'If this stays at 0, it is likely because your \'worse\' files are being deleted and so are leaving this file domain!' )
        self._num_same_quality_duplicates = ClientGUICommon.BetterStaticText( self._filtering_panel )
        self._num_alternate_duplicates = ClientGUICommon.BetterStaticText( self._filtering_panel )
        self._show_some_dupes = ClientGUICommon.BetterButton( self._filtering_panel, 'show some random pairs', self._ShowSomeDupes )
        self._launch_filter = ClientGUICommon.BetterButton( self._filtering_panel, 'launch the filter', self._LaunchFilter )
        
        #
        
        new_options = self._controller.GetNewOptions()
        
        self._search_distance_spinctrl.SetValue( new_options.GetInteger( 'similar_files_duplicate_pairs_search_distance' ) )
        
        duplicate_filter_file_domain = management_controller.GetKey( 'duplicate_filter_file_domain' )
        
        wx.CallAfter( self._SetFileDomain, duplicate_filter_file_domain ) # this spawns a refreshandupdatestatus
        
        #
        
        self._sort_by.Hide()
        self._collect_by.Hide()
        
        gridbox_1 = wx.FlexGridSizer( 0, 3 )
        
        gridbox_1.AddGrowableCol( 0, 1 )
        
        gridbox_1.AddF( self._num_phashes_to_regen, CC.FLAGS_VCENTER )
        gridbox_1.AddF( ( 10, 10 ), CC.FLAGS_EXPAND_PERPENDICULAR )
        gridbox_1.AddF( self._phashes_button, CC.FLAGS_VCENTER )
        gridbox_1.AddF( self._num_branches_to_regen, CC.FLAGS_VCENTER )
        gridbox_1.AddF( ( 10, 10 ), CC.FLAGS_EXPAND_PERPENDICULAR )
        gridbox_1.AddF( self._branches_button, CC.FLAGS_VCENTER )
        
        self._preparing_panel.AddF( gridbox_1, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        
        #
        
        distance_hbox = wx.BoxSizer( wx.HORIZONTAL )
        
        distance_hbox.AddF( ClientGUICommon.BetterStaticText( self._searching_panel, label = 'search distance: ' ), CC.FLAGS_VCENTER )
        distance_hbox.AddF( self._search_distance_button, CC.FLAGS_EXPAND_BOTH_WAYS )
        distance_hbox.AddF( self._search_distance_spinctrl, CC.FLAGS_VCENTER )
        
        gridbox_2 = wx.FlexGridSizer( 0, 2 )
        
        gridbox_2.AddGrowableCol( 0, 1 )
        
        gridbox_2.AddF( self._num_searched, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        gridbox_2.AddF( self._search_button, CC.FLAGS_VCENTER )
        
        self._searching_panel.AddF( distance_hbox, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        self._searching_panel.AddF( gridbox_2, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        
        #
        
        self._filtering_panel.AddF( self._file_domain_button, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._filtering_panel.AddF( self._num_unknown_duplicates, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._filtering_panel.AddF( self._num_better_duplicates, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._filtering_panel.AddF( self._num_same_quality_duplicates, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._filtering_panel.AddF( self._num_alternate_duplicates, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._filtering_panel.AddF( self._show_some_dupes, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._filtering_panel.AddF( self._launch_filter, CC.FLAGS_EXPAND_PERPENDICULAR )
        
        #
        
        hbox = wx.BoxSizer( wx.HORIZONTAL )
        
        hbox.AddF( self._cog_button, CC.FLAGS_VCENTER )
        hbox.AddF( self._help_button, CC.FLAGS_VCENTER )
        
        vbox = wx.BoxSizer( wx.VERTICAL )
        
        vbox.AddF( hbox, CC.FLAGS_BUTTON_SIZER )
        vbox.AddF( self._preparing_panel, CC.FLAGS_EXPAND_PERPENDICULAR )
        vbox.AddF( self._searching_panel, CC.FLAGS_EXPAND_PERPENDICULAR )
        vbox.AddF( self._filtering_panel, CC.FLAGS_EXPAND_PERPENDICULAR )
        
        self.SetSizer( vbox )
        
        self.Bind( wx.EVT_TIMER, self.TIMEREventUpdateDBJob, id = ID_TIMER_UPDATE )
        self._update_db_job_timer = wx.Timer( self, id = ID_TIMER_UPDATE )
        
        HG.client_controller.sub( self, 'RefreshAndUpdateStatus', 'refresh_dupe_numbers' )
        
    
    def _FileDomainButtonHit( self ):
        
        services_manager = HG.client_controller.services_manager
        
        services = []
        
        services.append( services_manager.GetService( CC.LOCAL_FILE_SERVICE_KEY ) )
        services.append( services_manager.GetService( CC.TRASH_SERVICE_KEY ) )
        services.append( services_manager.GetService( CC.COMBINED_LOCAL_FILE_SERVICE_KEY ) )
        
        menu = wx.Menu()
        
        for service in services:
            
            call = HydrusData.Call( self._SetFileDomain, service.GetServiceKey() )
            
            ClientGUIMenus.AppendMenuItem( self, menu, service.GetName(), 'Set the filtering file domain.', call )
            
        
        HG.client_controller.PopupMenu( self._file_domain_button, menu )
        
    
    def _LaunchFilter( self ):
        
        duplicate_filter_file_domain = self._management_controller.GetKey( 'duplicate_filter_file_domain' )
        
        canvas_frame = ClientGUICanvas.CanvasFrame( self.GetTopLevelParent() )
        
        canvas_window = ClientGUICanvas.CanvasFilterDuplicates( canvas_frame, duplicate_filter_file_domain )
        
        canvas_frame.SetCanvas( canvas_window )
        
    
    def _RebalanceTree( self ):
        
        self._job = 'branches'
        
        self._StartStopDBJob()
        
    
    def _RefreshAndUpdateStatus( self ):
        
        duplicate_filter_file_domain = self._management_controller.GetKey( 'duplicate_filter_file_domain' )
        
        self._similar_files_maintenance_status = self._controller.Read( 'similar_files_maintenance_status', duplicate_filter_file_domain )
        
        self._UpdateStatus()
        
    
    def _RegeneratePhashes( self ):
        
        self._job = 'phashes'
        
        self._StartStopDBJob()
        
    
    def _ResetUnknown( self ):
        
        text = 'This will delete all the potential duplicate pairs and reset their files\' search status.'
        text += os.linesep * 2
        text += 'This can be useful if you have accidentally searched too broadly and are now swamped with too many false positives.'
        
        with ClientGUIDialogs.DialogYesNo( self, text ) as dlg:
            
            if dlg.ShowModal() == wx.ID_YES:
                
                self._controller.Write( 'delete_unknown_duplicate_pairs' )
                
                self._RefreshAndUpdateStatus()
            
        
    
    def _SearchForDuplicates( self ):
        
        self._job = 'search'
        
        self._StartStopDBJob()
        
    
    def _SetFileDomain( self, service_key ):
        
        self._management_controller.SetKey( 'duplicate_filter_file_domain', service_key )
        
        services_manager = HG.client_controller.services_manager
        
        service = services_manager.GetService( service_key )
        
        self._file_domain_button.SetLabelText( service.GetName() )
        
        self._RefreshAndUpdateStatus()
        
    
    def _SetSearchDistance( self, value ):
        
        self._search_distance_spinctrl.SetValue( value )
        
        self._UpdateStatus()
        
    
    def _ShowSimpleHelp( self ):
        
        message = 'This page helps you discover and manage files that are very similar to each other. Sometimes these files will be exactly the same--but perhaps have a different resolution or image quality--or they may be recolours or have other small alterations. Here you can quickly define these relationships and hence merge your tags and ratings and, if you wish, delete the \'bad\' files.'
        message += os.linesep * 2
        message += 'There are three steps to this page:'
        message += os.linesep * 2
        message += '1 - Preparing the database for the CPU-heavy job of searching for duplicates.'
        message += os.linesep
        message += '2 - Performing the search and saving the results.'
        message += os.linesep
        message += '3 - Walking through the pairs or groups of potential duplicates and telling the client how they are related.'
        message += os.linesep * 2
        message += 'For the first two steps, you likely just want to click the play buttons and wait for them to complete. They are very CPU intensive and lock the database heavily as they work. If you want to use the client for anything else while they are running, pause them first. You can also set them to run in idle time from the cog icon. For the search \'distance\', start at the fast and limited \'exact match\', or 0 \'hamming distance\' search and slowly expand it as you gain experience with the system.'
        message += os.linesep * 2
        message += 'Once you have found some potential pairs, you can either show some random groups as thumbnails (and process them manually however you prefer), or you can launch the specialised duplicate filter, which lets you quickly assign duplicate status to pairs of files and will automatically merge files and tags between dupes however you prefer.'
        message += os.linesep * 2
        message += 'After launching the duplicate filter, check the keyboard and cog icons on its top hover window. They will let you assign default content merge options (including whether you wish to trash \'bad\' files) and also change the shortcuts for setting the different duplicate statuses. It works like the archive/delete filter, with left-click setting \'this is better\' and right-click setting \'alternates\' by default.'
        message += os.linesep * 2
        message += 'A list of the different duplicate statuses and their meanings will follow this message.'
        
        wx.MessageBox( message )
        
        message = 'The currently supported duplicate statuses are:'
        message += os.linesep * 2
        message += 'potential - This is the default state newly discovered pairs are assigned. They will be loaded in the filter for you to look at.'
        message += os.linesep * 2
        message += 'better/worse - This tells the client that the pair of files are duplicates--but the one you are looking at has better image quality or resolution or lacks an annoying watermark or so on.'
        message += os.linesep * 2
        message += 'same quality - This tells the client that the pair of files are duplicates, and that you cannot discern an obvious quality difference.'
        message += os.linesep * 2
        message += 'alternates - This tells the client that the pair of files are not duplicates but that they are related--perhaps they are a recolour or are an artist\'s different versions of a particular scene. A future version of the client will allow you to further process these alternate groups into family structures and so on.'
        message += os.linesep * 2
        message += 'not duplicates - This tells the client that the discovered pair is a false positive--they are not the same and are not otherwise related. This usually happens when the same part of two files have a similar shape by accident, such as if a hair fringe and a mountain range happen to line up.'
        
        wx.MessageBox( message )
        
    
    def _ShowSomeDupes( self ):
        
        duplicate_filter_file_domain = self._management_controller.GetKey( 'duplicate_filter_file_domain' )
        
        hashes = self._controller.Read( 'duplicate_hashes', duplicate_filter_file_domain, None, HC.DUPLICATE_UNKNOWN )
        
        media_results = self._controller.Read( 'media_results', hashes )
        
        panel = ClientGUIMedia.MediaPanelThumbnails( self._page, self._page_key, CC.COMBINED_LOCAL_FILE_SERVICE_KEY, media_results )
        
        self._controller.pub( 'swap_media_panel', self._page_key, panel )
        
    
    def _StartStopDBJob( self ):
        
        if self._job_key is None:
            
            self._cog_button.Disable()
            self._phashes_button.Disable()
            self._branches_button.Disable()
            self._search_button.Disable()
            self._search_distance_button.Disable()
            self._search_distance_spinctrl.Disable()
            self._show_some_dupes.Disable()
            self._launch_filter.Disable()
            
            self._job_key = ClientThreading.JobKey( cancellable = True )
            
            if self._job == 'phashes':
                
                self._phashes_button.Enable()
                self._phashes_button.SetBitmap( CC.GlobalBMPs.stop )
                
                self._controller.Write( 'maintain_similar_files_phashes', job_key = self._job_key )
                
            elif self._job == 'branches':
                
                self._branches_button.Enable()
                self._branches_button.SetBitmap( CC.GlobalBMPs.stop )
                
                self._controller.Write( 'maintain_similar_files_tree', job_key = self._job_key )
                
            elif self._job == 'search':
                
                self._search_button.Enable()
                self._search_button.SetBitmap( CC.GlobalBMPs.stop )
                
                search_distance = self._search_distance_spinctrl.GetValue()
                
                self._controller.Write( 'maintain_similar_files_duplicate_pairs', search_distance, job_key = self._job_key )
                
            
            self._update_db_job_timer.Start( 250, wx.TIMER_CONTINUOUS )
            
        else:
            
            self._job_key.Cancel()
            
        
    
    def _UpdateJob( self ):
        
        if self._in_break:
            
            if HG.client_controller.DBCurrentlyDoingJob():
                
                return
                
            else:
                
                self._in_break = False
                
                self._StartStopDBJob()
                
                return
                
            
        
        if self._job_key.TimeRunning() > 10:
            
            self._job_key.Cancel()
            
            self._job_key = None
            
            self._in_break = True
            
            return
            
        
        if self._job_key.IsDone():
            
            self._job_key = None
            
            self._update_db_job_timer.Stop()
            
            self._RefreshAndUpdateStatus()
            
            return
            
        
        if self._job == 'phashes':
            
            text = self._job_key.GetIfHasVariable( 'popup_text_1' )
            
            if text is not None:
                
                self._num_phashes_to_regen.SetLabelText( text )
                
            
        elif self._job == 'branches':
            
            text = self._job_key.GetIfHasVariable( 'popup_text_1' )
            
            if text is not None:
                
                self._num_branches_to_regen.SetLabelText( text )
                
            
        elif self._job == 'search':
            
            text = self._job_key.GetIfHasVariable( 'popup_text_1' )
            gauge = self._job_key.GetIfHasVariable( 'popup_gauge_1' )
            
            if text is not None and gauge is not None:
                
                ( value, range ) = gauge
                
                self._num_searched.SetValue( text, value, range )
                
            
        
    
    def _UpdateStatus( self ):
        
        ( num_phashes_to_regen, num_branches_to_regen, searched_distances_to_count, duplicate_types_to_count ) = self._similar_files_maintenance_status
        
        self._cog_button.Enable()
        
        self._phashes_button.SetBitmap( CC.GlobalBMPs.play )
        self._branches_button.SetBitmap( CC.GlobalBMPs.play )
        self._search_button.SetBitmap( CC.GlobalBMPs.play )
        
        total_num_files = sum( searched_distances_to_count.values() )
        
        if num_phashes_to_regen == 0:
            
            self._num_phashes_to_regen.SetLabelText( 'All ' + HydrusData.ConvertIntToPrettyString( total_num_files ) + ' eligible files up to date!' )
            
            self._phashes_button.Disable()
            
        else:
            
            num_done = total_num_files - num_phashes_to_regen
            
            self._num_phashes_to_regen.SetLabelText( HydrusData.ConvertValueRangeToPrettyString( num_done, total_num_files ) + ' eligible files up to date.' )
            
            self._phashes_button.Enable()
            
        
        if num_branches_to_regen == 0:
            
            self._num_branches_to_regen.SetLabelText( 'Search tree is fast!' )
            
            self._branches_button.Disable()
            
        else:
            
            self._num_branches_to_regen.SetLabelText( HydrusData.ConvertIntToPrettyString( num_branches_to_regen ) + ' search branches to rebalance.' )
            
            self._branches_button.Enable()
            
        
        self._search_distance_button.Enable()
        self._search_distance_spinctrl.Enable()
        
        search_distance = self._search_distance_spinctrl.GetValue()
        
        new_options = self._controller.GetNewOptions()
        
        new_options.SetInteger( 'similar_files_duplicate_pairs_search_distance', search_distance )
        
        if search_distance in HC.hamming_string_lookup:
            
            button_label = HC.hamming_string_lookup[ search_distance ]
            
        else:
            
            button_label = 'custom'
            
        
        self._search_distance_button.SetLabelText( button_label )
        
        num_searched = sum( ( count for ( value, count ) in searched_distances_to_count.items() if value is not None and value >= search_distance ) )
        
        if num_searched == total_num_files:
            
            self._num_searched.SetValue( 'All potential duplicates found at this distance.', total_num_files, total_num_files )
            
            self._search_button.Disable()
            
        else:
            
            if num_searched == 0:
                
                self._num_searched.SetValue( 'Have not yet searched at this distance.', 0, total_num_files )
                
            else:
                
                self._num_searched.SetValue( 'Searched ' + HydrusData.ConvertValueRangeToPrettyString( num_searched, total_num_files ) + ' files at this distance.', num_searched, total_num_files )
                
            
            self._search_button.Enable()
            
        
        num_unknown = duplicate_types_to_count[ HC.DUPLICATE_UNKNOWN ]
        
        self._num_unknown_duplicates.SetLabelText( HydrusData.ConvertIntToPrettyString( num_unknown ) + ' potential pairs.' )
        self._num_better_duplicates.SetLabelText( HydrusData.ConvertIntToPrettyString( duplicate_types_to_count[ HC.DUPLICATE_BETTER ] ) + ' better/worse pairs.' )
        self._num_same_quality_duplicates.SetLabelText( HydrusData.ConvertIntToPrettyString( duplicate_types_to_count[ HC.DUPLICATE_SAME_QUALITY ] ) + ' same quality pairs.' )
        self._num_alternate_duplicates.SetLabelText( HydrusData.ConvertIntToPrettyString( duplicate_types_to_count[ HC.DUPLICATE_ALTERNATE ] ) + ' alternate pairs.' )
        
        if num_unknown > 0:
            
            self._show_some_dupes.Enable()
            self._launch_filter.Enable()
            
        else:
            
            self._show_some_dupes.Disable()
            self._launch_filter.Disable()
            
        
    
    def EventSearchDistanceChanged( self, event ):
        
        self._UpdateStatus()
        
    
    def RefreshAndUpdateStatus( self ):
        
        self._RefreshAndUpdateStatus()
        
    
    def TIMEREventUpdateDBJob( self, event ):
        
        self._UpdateJob()
        
    
management_panel_types_to_classes[ MANAGEMENT_TYPE_DUPLICATE_FILTER ] = ManagementPanelDuplicateFilter

class ManagementPanelImporter( ManagementPanel ):
    
    def __init__( self, parent, page, controller, management_controller ):
        
        ManagementPanel.__init__( self, parent, page, controller, management_controller )
        
        self.Bind( wx.EVT_TIMER, self.TIMEREventImportUpdate, id = ID_TIMER_UPDATE )
        self._import_update_timer = wx.Timer( self, id = ID_TIMER_UPDATE )
        
        self._import_update_timer.Start( 250, wx.TIMER_CONTINUOUS )
        
    
    def _UpdateStatus( self ):
        
        raise NotImplementedError()
        
    
    def TIMEREventImportUpdate( self, event ):
        
        if self._controller.gui.IsCurrentPage( self._page_key ):
            
            self._UpdateStatus()
            
        
    
class ManagementPanelImporterGallery( ManagementPanelImporter ):
    
    def __init__( self, parent, page, controller, management_controller ):
        
        ManagementPanelImporter.__init__( self, parent, page, controller, management_controller )
        
        self._gallery_import = self._management_controller.GetVariable( 'gallery_import' )
        
        self._gallery_downloader_panel = ClientGUICommon.StaticBox( self, 'gallery downloader' )
        
        self._import_queue_panel = ClientGUICommon.StaticBox( self._gallery_downloader_panel, 'imports' )
        
        self._current_action = ClientGUICommon.BetterStaticText( self._import_queue_panel )
        self._seed_cache_control = ClientGUISeedCache.SeedCacheStatusControl( self._import_queue_panel, self._controller )
        self._file_download_control = ClientGUIControls.NetworkJobControl( self._import_queue_panel )
        
        self._files_pause_button = wx.BitmapButton( self._import_queue_panel, bitmap = CC.GlobalBMPs.pause )
        self._files_pause_button.Bind( wx.EVT_BUTTON, self.EventFilesPause )
        
        self._gallery_panel = ClientGUICommon.StaticBox( self._gallery_downloader_panel, 'gallery parser' )
        
        self._gallery_status = ClientGUICommon.BetterStaticText( self._gallery_panel )
        
        self._gallery_download_control = ClientGUIControls.NetworkJobControl( self._gallery_panel )
        
        self._gallery_pause_button = wx.BitmapButton( self._gallery_panel, bitmap = CC.GlobalBMPs.pause )
        self._gallery_pause_button.Bind( wx.EVT_BUTTON, self.EventGalleryPause )
        
        self._gallery_cancel_button = wx.BitmapButton( self._gallery_panel, bitmap = CC.GlobalBMPs.stop )
        self._gallery_cancel_button.Bind( wx.EVT_BUTTON, self.EventGalleryCancel )
        
        self._pending_queries_panel = ClientGUICommon.StaticBox( self._gallery_downloader_panel, 'pending queries' )
        
        self._pending_queries_listbox = wx.ListBox( self._pending_queries_panel, size = ( -1, 100 ) )
        
        self._advance_button = wx.Button( self._pending_queries_panel, label = u'\u2191' )
        self._advance_button.Bind( wx.EVT_BUTTON, self.EventAdvance )
        
        self._delete_button = wx.Button( self._pending_queries_panel, label = 'X' )
        self._delete_button.Bind( wx.EVT_BUTTON, self.EventDelete )
        
        self._delay_button = wx.Button( self._pending_queries_panel, label = u'\u2193' )
        self._delay_button.Bind( wx.EVT_BUTTON, self.EventDelay )
        
        self._query_input = wx.TextCtrl( self._pending_queries_panel, style = wx.TE_PROCESS_ENTER )
        self._query_input.Bind( wx.EVT_KEY_DOWN, self.EventKeyDown )
        
        self._query_paste = wx.Button( self._pending_queries_panel, label = 'paste queries' )
        self._query_paste.Bind( wx.EVT_BUTTON, self.EventPaste )
        
        menu_items = []
        
        invert_call = self._gallery_import.InvertGetTagsIfURLKnownAndFileRedundant
        value_call = self._gallery_import.GetTagsIfURLKnownAndFileRedundant
        
        check_manager = ClientGUICommon.CheckboxManagerCalls( invert_call, value_call )
        
        menu_items.append( ( 'check', 'get tags even if url is known and file is already in db (this downloader)', 'If this is selected, the client will fetch the tags from a file\'s page even if it has the file and already previously downloaded it from that location.', check_manager ) )
        
        menu_items.append( ( 'separator', 0, 0, 0 ) )
        
        check_manager = ClientGUICommon.CheckboxManagerOptions( 'get_tags_if_url_known_and_file_redundant' )
        
        menu_items.append( ( 'check', 'get tags even if url is known and file is already in db (default)', 'Set the default for this value.', check_manager ) )
        
        self._cog_button = ClientGUICommon.MenuBitmapButton( self._gallery_downloader_panel, CC.GlobalBMPs.cog, menu_items )
        
        self._file_limit = ClientGUICommon.NoneableSpinCtrl( self._gallery_downloader_panel, 'stop after this many files', min = 1, none_phrase = 'no limit' )
        self._file_limit.Bind( wx.EVT_SPINCTRL, self.EventFileLimit )
        self._file_limit.SetToolTipString( 'per query, stop searching the gallery once this many files has been reached' )
        
        self._import_file_options = ClientGUICollapsible.CollapsibleOptionsImportFiles( self._gallery_downloader_panel )
        self._import_tag_options = ClientGUICollapsible.CollapsibleOptionsTags( self._gallery_downloader_panel )
        
        #
        
        button_sizer = wx.BoxSizer( wx.HORIZONTAL )
        
        button_sizer.AddF( self._gallery_pause_button, CC.FLAGS_VCENTER )
        button_sizer.AddF( self._gallery_cancel_button, CC.FLAGS_VCENTER )
        
        self._gallery_panel.AddF( self._gallery_status, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._gallery_panel.AddF( self._gallery_download_control, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._gallery_panel.AddF( button_sizer, CC.FLAGS_LONE_BUTTON )
        
        #
        
        queue_buttons_vbox = wx.BoxSizer( wx.VERTICAL )
        
        queue_buttons_vbox.AddF( self._advance_button, CC.FLAGS_VCENTER )
        queue_buttons_vbox.AddF( self._delete_button, CC.FLAGS_VCENTER )
        queue_buttons_vbox.AddF( self._delay_button, CC.FLAGS_VCENTER )
        
        queue_hbox = wx.BoxSizer( wx.HORIZONTAL )
        
        queue_hbox.AddF( self._pending_queries_listbox, CC.FLAGS_EXPAND_BOTH_WAYS )
        queue_hbox.AddF( queue_buttons_vbox, CC.FLAGS_VCENTER )
        
        input_hbox = wx.BoxSizer( wx.HORIZONTAL )
        
        input_hbox.AddF( self._query_input, CC.FLAGS_EXPAND_BOTH_WAYS )
        input_hbox.AddF( self._query_paste, CC.FLAGS_VCENTER )
        
        self._pending_queries_panel.AddF( queue_hbox, CC.FLAGS_EXPAND_SIZER_BOTH_WAYS )
        self._pending_queries_panel.AddF( input_hbox, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        
        #
        
        self._import_queue_panel.AddF( self._current_action, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._import_queue_panel.AddF( self._seed_cache_control, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._import_queue_panel.AddF( self._file_download_control, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._import_queue_panel.AddF( self._files_pause_button, CC.FLAGS_LONE_BUTTON )
        
        self._gallery_downloader_panel.AddF( self._import_queue_panel, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._gallery_downloader_panel.AddF( self._gallery_panel, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._gallery_downloader_panel.AddF( self._pending_queries_panel, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._gallery_downloader_panel.AddF( self._cog_button, CC.FLAGS_LONE_BUTTON )
        self._gallery_downloader_panel.AddF( self._file_limit, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._gallery_downloader_panel.AddF( self._import_file_options, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._gallery_downloader_panel.AddF( self._import_tag_options, CC.FLAGS_EXPAND_PERPENDICULAR )
        
        #
        
        vbox = wx.BoxSizer( wx.VERTICAL )
        
        vbox.AddF( self._sort_by, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        
        self._collect_by.Hide()
        
        vbox.AddF( self._gallery_downloader_panel, CC.FLAGS_EXPAND_PERPENDICULAR )
        
        self._MakeCurrentSelectionTagsBox( vbox )
        
        self.SetSizer( vbox )
        
        #
        
        self.Bind( wx.EVT_MENU, self.EventMenu )
        
        gallery_identifier = self._gallery_import.GetGalleryIdentifier()
        
        ( namespaces, search_value ) = ClientDefaults.GetDefaultNamespacesAndSearchValue( gallery_identifier )
        
        seed_cache = self._gallery_import.GetSeedCache()
        
        self._seed_cache_control.SetSeedCache( seed_cache )
        
        self._import_tag_options.SetNamespaces( namespaces )
        self._query_input.SetValue( search_value )
        
        self._gallery_import.SetDownloadControls( self._file_download_control, self._gallery_download_control )
        
        ( import_file_options, import_tag_options, file_limit ) = self._gallery_import.GetOptions()
        
        self._import_file_options.SetOptions( import_file_options )
        self._import_tag_options.SetOptions( import_tag_options )
        
        self._file_limit.SetValue( file_limit )
        
        self._UpdateStatus()
        
    
    def _SeedCache( self ):
        
        seed_cache = self._gallery_import.GetSeedCache()
        
        title = 'file import status'
        frame_key = 'file_import_status'
        
        frame = ClientGUITopLevelWindows.FrameThatTakesScrollablePanel( self, title, frame_key )
        
        panel = ClientGUISeedCache.EditSeedCachePanel( frame, self._controller, seed_cache )
        
        frame.SetPanel( panel )
        
    
    def _UpdateStatus( self ):
        
        ( pending_queries, gallery_status, current_action, files_paused, gallery_paused, gallery_cancellable ) = self._gallery_import.GetStatus()
        
        if self._pending_queries_listbox.GetStrings() != pending_queries:
            
            selected_string = self._pending_queries_listbox.GetStringSelection()
            
            self._pending_queries_listbox.SetItems( pending_queries )
            
            selection_index = self._pending_queries_listbox.FindString( selected_string )
            
            if selection_index != wx.NOT_FOUND:
                
                self._pending_queries_listbox.Select( selection_index )
                
            
        
        if files_paused:
            
            if self._files_pause_button.GetBitmap() != CC.GlobalBMPs.play:
                
                self._files_pause_button.SetBitmap( CC.GlobalBMPs.play )
                
            
        else:
            
            if self._files_pause_button.GetBitmap() != CC.GlobalBMPs.pause:
                
                self._files_pause_button.SetBitmap( CC.GlobalBMPs.pause )
                
            
        
        if gallery_paused:
            
            if self._gallery_pause_button.GetBitmap() != CC.GlobalBMPs.play:
                
                self._gallery_pause_button.SetBitmap( CC.GlobalBMPs.play )
                
            
        else:
            
            if self._gallery_pause_button.GetBitmap() != CC.GlobalBMPs.pause:
                
                self._gallery_pause_button.SetBitmap( CC.GlobalBMPs.pause )
                
            
        
        if gallery_cancellable:
            
            self._gallery_cancel_button.Enable()
            
        else:
            
            self._gallery_cancel_button.Disable()
            
        
        if gallery_paused:
            
            if gallery_status == '':
                
                gallery_status = 'paused'
                
            else:
                
                gallery_status = 'paused - ' + gallery_status
                
            
        
        self._gallery_status.SetLabelText( gallery_status )
        
        if files_paused:
            
            if current_action == '':
                
                current_action = 'paused'
                
            else:
                
                current_action = 'pausing - ' + current_action
                
            
        
        self._current_action.SetLabelText( current_action )
        
    
    def EventAdvance( self, event ):
        
        selection = self._pending_queries_listbox.GetSelection()
        
        if selection != wx.NOT_FOUND:
            
            query = self._pending_queries_listbox.GetString( selection )
            
            self._gallery_import.AdvanceQuery( query )
            
            self._UpdateStatus()
            
        
    
    def EventDelay( self, event ):
        
        selection = self._pending_queries_listbox.GetSelection()
        
        if selection != wx.NOT_FOUND:
            
            query = self._pending_queries_listbox.GetString( selection )
            
            self._gallery_import.DelayQuery( query )
            
            self._UpdateStatus()
            
        
    
    def EventDelete( self, event ):
        
        selection = self._pending_queries_listbox.GetSelection()
        
        if selection != wx.NOT_FOUND:
            
            query = self._pending_queries_listbox.GetString( selection )
            
            self._gallery_import.DeleteQuery( query )
            
            self._UpdateStatus()
            
        
    
    def EventFileLimit( self, event ):
        
        self._gallery_import.SetFileLimit( self._file_limit.GetValue() )
        
        event.Skip()
        
    
    def EventFilesPause( self, event ):
        
        self._gallery_import.PausePlayFiles()
        
        self._UpdateStatus()
        
    
    def EventGalleryCancel( self, event ):
        
        self._gallery_import.FinishCurrentQuery()
        
        self._UpdateStatus()
        
    
    def EventGalleryPause( self, event ):
        
        self._gallery_import.PausePlayGallery()
        
        self._UpdateStatus()
        
    
    def EventKeyDown( self, event ):
        
        ( modifier, key ) = ClientData.ConvertKeyEventToSimpleTuple( event )
        
        if key in ( wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER ):
            
            query = self._query_input.GetValue()
            
            if query != '':
                
                self._gallery_import.PendQuery( query )
                
            
            self._query_input.SetValue( '' )
            
            self._UpdateStatus()
            
        else:
            
            event.Skip()
            
        
    
    def EventMenu( self, event ):
        
        action = ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetAction( event.GetId() )
        
        if action is not None:
            
            ( command, data ) = action
            
            if command == 'import_file_options_changed':
                
                import_file_options = self._import_file_options.GetOptions()
                
                self._gallery_import.SetImportFileOptions( import_file_options )
                
            if command == 'import_tag_options_changed':
                
                import_tag_options = self._import_tag_options.GetOptions()
                
                self._gallery_import.SetImportTagOptions( import_tag_options )
                
            else:
                
                event.Skip()
                
            
        
    
    def EventPaste( self, event ):
        
        if wx.TheClipboard.Open():
            
            data = wx.TextDataObject()
            
            wx.TheClipboard.GetData( data )
            
            wx.TheClipboard.Close()
            
            raw_text = data.GetText()
            
            try:
                
                for query in HydrusData.SplitByLinesep( raw_text ):
                    
                    if query != '':
                        
                        self._gallery_import.PendQuery( query )
                        
                    
                
                self._UpdateStatus()
                
            except:
                
                wx.MessageBox( 'I could not understand what was in the clipboard' )
                
            
        else:
            
            wx.MessageBox( 'I could not get permission to access the clipboard.' )
            
        
    
    def SetSearchFocus( self, page_key ):
        
        if page_key == self._page_key:
            
            self._query_input.SetFocus()
            
        
    
    def Start( self ):
        
        self._gallery_import.Start( self._page_key )
        
    
management_panel_types_to_classes[ MANAGEMENT_TYPE_IMPORT_GALLERY ] = ManagementPanelImporterGallery

class ManagementPanelImporterHDD( ManagementPanelImporter ):
    
    def __init__( self, parent, page, controller, management_controller ):
        
        ManagementPanelImporter.__init__( self, parent, page, controller, management_controller )
        
        self._import_queue_panel = ClientGUICommon.StaticBox( self, 'import summary' )
        
        self._current_action = ClientGUICommon.BetterStaticText( self._import_queue_panel )
        self._seed_cache_control = ClientGUISeedCache.SeedCacheStatusControl( self._import_queue_panel, self._controller )
        
        self._pause_button = wx.BitmapButton( self._import_queue_panel, bitmap = CC.GlobalBMPs.pause )
        self._pause_button.Bind( wx.EVT_BUTTON, self.EventPause )
        
        #
        
        vbox = wx.BoxSizer( wx.VERTICAL )
        
        vbox.AddF( self._sort_by, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        
        self._collect_by.Hide()
        
        self._import_queue_panel.AddF( self._current_action, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._import_queue_panel.AddF( self._seed_cache_control, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._import_queue_panel.AddF( self._pause_button, CC.FLAGS_LONE_BUTTON )
        
        vbox.AddF( self._import_queue_panel, CC.FLAGS_EXPAND_PERPENDICULAR )
        
        self._MakeCurrentSelectionTagsBox( vbox )
        
        self.SetSizer( vbox )
        
        #
        
        self._hdd_import = self._management_controller.GetVariable( 'hdd_import' )
        
        seed_cache = self._hdd_import.GetSeedCache()
        
        self._seed_cache_control.SetSeedCache( seed_cache )
        
        self._UpdateStatus()
        
    
    def _UpdateStatus( self ):
        
        ( current_action, paused ) = self._hdd_import.GetStatus()
        
        if paused:
            
            if self._pause_button.GetBitmap() != CC.GlobalBMPs.play:
                
                self._pause_button.SetBitmap( CC.GlobalBMPs.play )
                
            
        else:
            
            if self._pause_button.GetBitmap() != CC.GlobalBMPs.pause:
                
                self._pause_button.SetBitmap( CC.GlobalBMPs.pause )
                
            
        
        if paused:
            
            if current_action == '':
                
                current_action = 'paused'
                
            else:
                
                current_action = 'pausing - ' + current_action
                
            
        
        self._current_action.SetLabelText( current_action )
        
    
    def EventPause( self, event ):
        
        self._hdd_import.PausePlay()
        
        self._UpdateStatus()
        
    
    def Start( self ):
        
        self._hdd_import.Start( self._page_key )
        
    
    def TestAbleToClose( self ):
        
        if self._hdd_import.CurrentlyWorking():
            
            with ClientGUIDialogs.DialogYesNo( self, 'This page is still importing. Are you sure you want to close it?' ) as dlg:
                
                if dlg.ShowModal() == wx.ID_NO:
                    
                    raise HydrusExceptions.PermissionException()
                    
                
            
        
    
management_panel_types_to_classes[ MANAGEMENT_TYPE_IMPORT_HDD ] = ManagementPanelImporterHDD

class ManagementPanelImporterPageOfImages( ManagementPanelImporter ):
    
    def __init__( self, parent, page, controller, management_controller ):
        
        ManagementPanelImporter.__init__( self, parent, page, controller, management_controller )
        
        self._page_of_images_panel = ClientGUICommon.StaticBox( self, 'page of images downloader' )
        
        self._pause_button = wx.BitmapButton( self._page_of_images_panel, bitmap = CC.GlobalBMPs.pause )
        self._pause_button.Bind( wx.EVT_BUTTON, self.EventPause )
        
        #
        
        self._import_queue_panel = ClientGUICommon.StaticBox( self._page_of_images_panel, 'imports' )
        
        self._current_action = ClientGUICommon.BetterStaticText( self._import_queue_panel )
        self._seed_cache_control = ClientGUISeedCache.SeedCacheStatusControl( self._import_queue_panel, self._controller )
        self._file_download_control = ClientGUIControls.NetworkJobControl( self._import_queue_panel )
        
        self._pending_page_urls_panel = ClientGUICommon.StaticBox( self._page_of_images_panel, 'pending page urls' )
        
        self._parser_status = ClientGUICommon.BetterStaticText( self._pending_page_urls_panel )
        
        self._page_download_control = ClientGUIControls.NetworkJobControl( self._pending_page_urls_panel )
        
        self._pending_page_urls_listbox = wx.ListBox( self._pending_page_urls_panel, size = ( -1, 100 ) )
        
        self._advance_button = wx.Button( self._pending_page_urls_panel, label = u'\u2191' )
        self._advance_button.Bind( wx.EVT_BUTTON, self.EventAdvance )
        
        self._delete_button = wx.Button( self._pending_page_urls_panel, label = 'X' )
        self._delete_button.Bind( wx.EVT_BUTTON, self.EventDelete )
        
        self._delay_button = wx.Button( self._pending_page_urls_panel, label = u'\u2193' )
        self._delay_button.Bind( wx.EVT_BUTTON, self.EventDelay )
        
        self._page_url_input = wx.TextCtrl( self._pending_page_urls_panel, style = wx.TE_PROCESS_ENTER )
        self._page_url_input.Bind( wx.EVT_KEY_DOWN, self.EventKeyDown )
        
        self._page_url_paste = wx.Button( self._pending_page_urls_panel, label = 'paste urls' )
        self._page_url_paste.Bind( wx.EVT_BUTTON, self.EventPaste )
        
        self._download_image_links = wx.CheckBox( self._page_of_images_panel, label = 'download image links' )
        self._download_image_links.Bind( wx.EVT_CHECKBOX, self.EventDownloadImageLinks )
        self._download_image_links.SetToolTipString( 'i.e. download the href url of an <a> tag if there is an <img> tag nested beneath it' )
        
        self._download_unlinked_images = wx.CheckBox( self._page_of_images_panel, label = 'download unlinked images' )
        self._download_unlinked_images.Bind( wx.EVT_CHECKBOX, self.EventDownloadUnlinkedImages )
        self._download_unlinked_images.SetToolTipString( 'i.e. download the src url of an <img> tag if there is no parent <a> tag' )
        
        self._import_file_options = ClientGUICollapsible.CollapsibleOptionsImportFiles( self._page_of_images_panel )
        
        #
        
        queue_buttons_vbox = wx.BoxSizer( wx.VERTICAL )
        
        queue_buttons_vbox.AddF( self._advance_button, CC.FLAGS_VCENTER )
        queue_buttons_vbox.AddF( self._delete_button, CC.FLAGS_VCENTER )
        queue_buttons_vbox.AddF( self._delay_button, CC.FLAGS_VCENTER )
        
        queue_hbox = wx.BoxSizer( wx.HORIZONTAL )
        
        queue_hbox.AddF( self._pending_page_urls_listbox, CC.FLAGS_EXPAND_BOTH_WAYS )
        queue_hbox.AddF( queue_buttons_vbox, CC.FLAGS_VCENTER )
        
        input_hbox = wx.BoxSizer( wx.HORIZONTAL )
        
        input_hbox.AddF( self._page_url_input, CC.FLAGS_EXPAND_BOTH_WAYS )
        input_hbox.AddF( self._page_url_paste, CC.FLAGS_VCENTER )
        
        self._pending_page_urls_panel.AddF( self._parser_status, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._pending_page_urls_panel.AddF( self._page_download_control, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._pending_page_urls_panel.AddF( queue_hbox, CC.FLAGS_EXPAND_SIZER_BOTH_WAYS )
        self._pending_page_urls_panel.AddF( input_hbox, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        
        #
        
        self._import_queue_panel.AddF( self._current_action, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._import_queue_panel.AddF( self._seed_cache_control, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._import_queue_panel.AddF( self._file_download_control, CC.FLAGS_EXPAND_PERPENDICULAR )
        
        self._page_of_images_panel.AddF( self._pause_button, CC.FLAGS_LONE_BUTTON )
        self._page_of_images_panel.AddF( self._import_queue_panel, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._page_of_images_panel.AddF( self._pending_page_urls_panel, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._page_of_images_panel.AddF( self._download_image_links, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._page_of_images_panel.AddF( self._download_unlinked_images, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._page_of_images_panel.AddF( self._import_file_options, CC.FLAGS_EXPAND_PERPENDICULAR )
        
        #
        
        vbox = wx.BoxSizer( wx.VERTICAL )
        
        vbox.AddF( self._sort_by, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        
        self._collect_by.Hide()
        
        vbox.AddF( self._page_of_images_panel, CC.FLAGS_EXPAND_PERPENDICULAR )
        
        self._MakeCurrentSelectionTagsBox( vbox )
        
        self.SetSizer( vbox )
        
        #
        
        self.Bind( wx.EVT_MENU, self.EventMenu )
        
        self._page_of_images_import = self._management_controller.GetVariable( 'page_of_images_import' )
        
        seed_cache = self._page_of_images_import.GetSeedCache()
        
        self._seed_cache_control.SetSeedCache( seed_cache )
        
        self._page_of_images_import.SetDownloadControlFile( self._file_download_control )
        self._page_of_images_import.SetDownloadControlPage( self._page_download_control )
        
        ( import_file_options, download_image_links, download_unlinked_images ) = self._page_of_images_import.GetOptions()
        
        self._import_file_options.SetOptions( import_file_options )
        
        self._download_image_links.SetValue( download_image_links )
        self._download_unlinked_images.SetValue( download_unlinked_images )
        
        self._UpdateStatus()
        
    
    def _SeedCache( self ):
        
        seed_cache = self._page_of_images_import.GetSeedCache()
        
        title = 'file import status'
        frame_key = 'file_import_status'
        
        frame = ClientGUITopLevelWindows.FrameThatTakesScrollablePanel( self, title, frame_key )
        
        panel = ClientGUISeedCache.EditSeedCachePanel( frame, self._controller, seed_cache )
        
        frame.SetPanel( panel )
        
    
    def _UpdateStatus( self ):
        
        ( pending_page_urls, parser_status, current_action, paused ) = self._page_of_images_import.GetStatus()
        
        if self._pending_page_urls_listbox.GetStrings() != pending_page_urls:
            
            selected_string = self._pending_page_urls_listbox.GetStringSelection()
            
            self._pending_page_urls_listbox.SetItems( pending_page_urls )
            
            selection_index = self._pending_page_urls_listbox.FindString( selected_string )
            
            if selection_index != wx.NOT_FOUND:
                
                self._pending_page_urls_listbox.Select( selection_index )
                
            
        
        if paused:
            
            parser_status = 'paused'
            
        
        self._parser_status.SetLabelText( parser_status )
        
        if current_action == '' and paused:
            
            current_action = 'paused'
            
        
        self._current_action.SetLabelText( current_action )
        
        if paused:
            
            if self._pause_button.GetBitmap() != CC.GlobalBMPs.play:
                
                self._pause_button.SetBitmap( CC.GlobalBMPs.play )
                
            
        else:
            
            if self._pause_button.GetBitmap() != CC.GlobalBMPs.pause:
                
                self._pause_button.SetBitmap( CC.GlobalBMPs.pause )
                
            
        
    
    def EventAdvance( self, event ):
        
        selection = self._pending_page_urls_listbox.GetSelection()
        
        if selection != wx.NOT_FOUND:
            
            page_url = self._pending_page_urls_listbox.GetString( selection )
            
            self._page_of_images_import.AdvancePageURL( page_url )
            
            self._UpdateStatus()
            
        
    
    def EventDelay( self, event ):
        
        selection = self._pending_page_urls_listbox.GetSelection()
        
        if selection != wx.NOT_FOUND:
            
            page_url = self._pending_page_urls_listbox.GetString( selection )
            
            self._page_of_images_import.DelayPageURL( page_url )
            
            self._UpdateStatus()
            
        
    
    def EventDelete( self, event ):
        
        selection = self._pending_page_urls_listbox.GetSelection()
        
        if selection != wx.NOT_FOUND:
            
            page_url = self._pending_page_urls_listbox.GetString( selection )
            
            self._page_of_images_import.DeletePageURL( page_url )
            
            self._UpdateStatus()
            
        
    
    def EventDownloadImageLinks( self, event ):
        
        self._page_of_images_import.SetDownloadImageLinks( self._download_image_links.GetValue() )
        
    
    def EventDownloadUnlinkedImages( self, event ):
        
        self._page_of_images_import.SetDownloadUnlinkedImages( self._download_unlinked_images.GetValue() )
        
    
    def EventKeyDown( self, event ):
        
        ( modifier, key ) = ClientData.ConvertKeyEventToSimpleTuple( event )
        
        if key in ( wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER ):
            
            page_url = self._page_url_input.GetValue()
            
            if page_url != '':
                
                self._page_of_images_import.PendPageURL( page_url )
                
                self._page_url_input.SetValue( '' )
                
                self._UpdateStatus()
                
            
        else:
            
            event.Skip()
            
        
    
    def EventMenu( self, event ):
        
        action = ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetAction( event.GetId() )
        
        if action is not None:
            
            ( command, data ) = action
            
            if command == 'import_file_options_changed':
                
                import_file_options = self._import_file_options.GetOptions()
                
                self._page_of_images_import.SetImportFileOptions( import_file_options )
                
            else: event.Skip()
            
        
    
    def EventPaste( self, event ):
    
        if wx.TheClipboard.Open():
            
            data = wx.TextDataObject()
            
            wx.TheClipboard.GetData( data )
            
            wx.TheClipboard.Close()
            
            raw_text = data.GetText()
            
            try:
                
                for page_url in HydrusData.SplitByLinesep( raw_text ):
                    
                    if page_url != '':
                        
                        self._page_of_images_import.PendPageURL( page_url )
                        
                    
                
                self._UpdateStatus()
                
            except:
                
                wx.MessageBox( 'I could not understand what was in the clipboard' )
                
            
        else:
            
            wx.MessageBox( 'I could not get permission to access the clipboard.' )
            
        
    
    def EventPause( self, event ):
        
        self._page_of_images_import.PausePlay()
        
        self._UpdateStatus()
        
    
    def SetSearchFocus( self, page_key ):
        
        if page_key == self._page_key: self._page_url_input.SetFocus()
        
    
    def Start( self ):
        
        self._page_of_images_import.Start( self._page_key )
        
    
    def TestAbleToClose( self ):
        
        if self._page_of_images_import.CurrentlyWorking():
            
            with ClientGUIDialogs.DialogYesNo( self, 'This page is still importing. Are you sure you want to close it?' ) as dlg:
                
                if dlg.ShowModal() == wx.ID_NO:
                    
                    raise HydrusExceptions.PermissionException()
                    
                
            
        
    
management_panel_types_to_classes[ MANAGEMENT_TYPE_IMPORT_PAGE_OF_IMAGES ] = ManagementPanelImporterPageOfImages

class ManagementPanelImporterThreadWatcher( ManagementPanelImporter ):
    
    def __init__( self, parent, page, controller, management_controller ):
        
        ManagementPanelImporter.__init__( self, parent, page, controller, management_controller )
        
        self._thread_watcher_panel = ClientGUICommon.StaticBox( self, 'thread watcher' )
        
        self._thread_input = wx.TextCtrl( self._thread_watcher_panel, style = wx.TE_PROCESS_ENTER )
        self._thread_input.Bind( wx.EVT_KEY_DOWN, self.EventKeyDown )
        
        self._options_panel = wx.Panel( self._thread_watcher_panel )
        
        self._pause_button = wx.BitmapButton( self._options_panel, bitmap = CC.GlobalBMPs.pause )
        self._pause_button.Bind( wx.EVT_BUTTON, self.EventPause )
        
        #
        
        imports_panel = ClientGUICommon.StaticBox( self._options_panel, 'imports' )
        
        self._current_action = ClientGUICommon.BetterStaticText( imports_panel )
        self._seed_cache_control = ClientGUISeedCache.SeedCacheStatusControl( imports_panel, self._controller )
        self._file_download_control = ClientGUIControls.NetworkJobControl( imports_panel )
        
        #
        
        checker_panel = ClientGUICommon.StaticBox( self._options_panel, 'checker' )
        
        self._watcher_status = ClientGUICommon.BetterStaticText( checker_panel )
        self._thread_download_control = ClientGUIControls.NetworkJobControl( checker_panel )
        
        ( times_to_check, check_period ) = HC.options[ 'thread_checker_timings' ]
        
        self._thread_times_to_check = wx.SpinCtrl( checker_panel, size = ( 60, -1 ), min = 0, max = 65536 )
        self._thread_times_to_check.SetValue( times_to_check )
        self._thread_times_to_check.Bind( wx.EVT_SPINCTRL, self.EventTimesToCheck )
        
        self._thread_check_period = ClientGUICommon.TimeDeltaButton( checker_panel, min = 30, days = True, hours = True, minutes = True, seconds = True )
        self._thread_check_period.SetValue( check_period )
        self._thread_check_period.Bind( ClientGUICommon.EVT_TIME_DELTA, self.EventCheckPeriod )
        
        self._thread_check_now_button = wx.Button( checker_panel, label = 'check now' )
        self._thread_check_now_button.Bind( wx.EVT_BUTTON, self.EventCheckNow )
        
        #
        
        self._import_file_options = ClientGUICollapsible.CollapsibleOptionsImportFiles( self._thread_watcher_panel )
        self._import_tag_options = ClientGUICollapsible.CollapsibleOptionsTags( self._thread_watcher_panel, namespaces = [ 'filename' ] )
        
        #
        
        imports_panel.AddF( self._current_action, CC.FLAGS_EXPAND_PERPENDICULAR )
        imports_panel.AddF( self._seed_cache_control, CC.FLAGS_EXPAND_PERPENDICULAR )
        imports_panel.AddF( self._file_download_control, CC.FLAGS_EXPAND_PERPENDICULAR )
        
        hbox_1 = wx.WrapSizer( wx.HORIZONTAL )
        
        hbox_1.AddF( ClientGUICommon.BetterStaticText( checker_panel, label = 'checking ' ), CC.FLAGS_VCENTER )
        hbox_1.AddF( self._thread_times_to_check, CC.FLAGS_VCENTER )
        hbox_1.AddF( ClientGUICommon.BetterStaticText( checker_panel, label = ' more times, every ' ), CC.FLAGS_VCENTER )
        hbox_1.AddF( self._thread_check_period, CC.FLAGS_VCENTER )
        hbox_1.AddF( self._thread_check_now_button, CC.FLAGS_VCENTER )
        
        checker_panel.AddF( self._watcher_status, CC.FLAGS_EXPAND_PERPENDICULAR )
        checker_panel.AddF( self._thread_download_control, CC.FLAGS_EXPAND_PERPENDICULAR )
        checker_panel.AddF( hbox_1, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        
        vbox = wx.BoxSizer( wx.VERTICAL )
        
        vbox.AddF( self._pause_button, CC.FLAGS_LONE_BUTTON )
        vbox.AddF( imports_panel, CC.FLAGS_EXPAND_PERPENDICULAR )
        vbox.AddF( checker_panel, CC.FLAGS_EXPAND_PERPENDICULAR )
        
        self._options_panel.SetSizer( vbox )
        
        self._thread_watcher_panel.AddF( self._thread_input, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._thread_watcher_panel.AddF( self._options_panel, CC.FLAGS_EXPAND_SIZER_BOTH_WAYS )
        self._thread_watcher_panel.AddF( self._import_file_options, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._thread_watcher_panel.AddF( self._import_tag_options, CC.FLAGS_EXPAND_PERPENDICULAR )
        
        #
        
        vbox = wx.BoxSizer( wx.VERTICAL )
        
        vbox.AddF( self._sort_by, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        
        self._collect_by.Hide()
        
        vbox.AddF( self._thread_watcher_panel, CC.FLAGS_EXPAND_PERPENDICULAR )
        
        self._MakeCurrentSelectionTagsBox( vbox )
        
        self.SetSizer( vbox )
        
        #
        
        self.Bind( wx.EVT_MENU, self.EventMenu )
        
        self._controller.sub( self, 'DecrementTimesToCheck', 'decrement_times_to_check' )
        
        self._thread_watcher_import = self._management_controller.GetVariable( 'thread_watcher_import' )
        
        seed_cache = self._thread_watcher_import.GetSeedCache()
        
        self._seed_cache_control.SetSeedCache( seed_cache )
        
        self._thread_watcher_import.SetDownloadControlFile( self._file_download_control )
        self._thread_watcher_import.SetDownloadControlThread( self._thread_download_control )
        
        ( thread_url, import_file_options, import_tag_options, times_to_check, check_period ) = self._thread_watcher_import.GetOptions()
        
        self._thread_input.SetValue( thread_url )
        
        self._import_file_options.SetOptions( import_file_options )
        self._import_tag_options.SetOptions( import_tag_options )
        
        self._thread_times_to_check.SetValue( times_to_check )
        self._thread_check_period.SetValue( check_period )
        
        self._UpdateStatus()
        
    
    def _UpdateStatus( self ):
        
        if self._thread_watcher_import.HasThread():
            
            self._thread_input.SetEditable( False )
            
            if not self._options_panel.IsShown():
                
                self._options_panel.Show()
                
                self.Layout()
                
            
        else:
            
            if self._options_panel.IsShown():
                
                self._options_panel.Hide()
                
                self.Layout()
                
            
        
        ( current_action, watcher_status, check_now, paused ) = self._thread_watcher_import.GetStatus()
        
        self._current_action.SetLabelText( current_action )
        
        if paused:
            
            if self._thread_times_to_check.GetValue() > 0 or check_now:
                
                watcher_status = 'paused'
                
            
            if self._pause_button.GetBitmap() != CC.GlobalBMPs.play:
                
                self._pause_button.SetBitmap( CC.GlobalBMPs.play )
                
            
        else:
            
            if self._pause_button.GetBitmap() != CC.GlobalBMPs.pause:
                
                self._pause_button.SetBitmap( CC.GlobalBMPs.pause )
                
            
        
        self._watcher_status.SetLabelText( watcher_status )
        
        if current_action == '' and paused:
            
            current_action = 'paused'
            
        
        if check_now:
            
            self._thread_check_now_button.Disable()
            
        else:
            
            self._thread_check_now_button.Enable()
            
        
    
    def DecrementTimesToCheck( self, page_key ):
        
        if page_key == self._page_key:
            
            current_value = self._thread_times_to_check.GetValue()
            
            new_value = max( 0, current_value - 1 )
            
            self._thread_times_to_check.SetValue( new_value )
            
        
    
    def EventCheckNow( self, event ):
        
        self._thread_watcher_import.CheckNow()
        
        self._UpdateStatus()
        
    
    def EventCheckPeriod( self, event ):
        
        check_period = self._thread_check_period.GetValue()
        
        self._thread_watcher_import.SetCheckPeriod( check_period )
        
    
    def EventKeyDown( self, event ):
        
        ( modifier, key ) = ClientData.ConvertKeyEventToSimpleTuple( event )
        
        if key in ( wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER ):
            
            thread_url = self._thread_input.GetValue()
            
            if thread_url == '':
                
                return
                
            
            try:
                
                ( thread_url, host, board, thread_id ) = ClientDownloading.ParseImageboardThreadURL( thread_url )
                
            except Exception as e:
                
                HydrusData.ShowException( e )
                
                return
                
            
            self._thread_input.SetEditable( False )
            
            self._thread_watcher_import.SetThreadURL( thread_url )
            
            self._thread_watcher_import.Start( self._page_key )
            
        else:
            
            event.Skip()
            
        
    
    def EventMenu( self, event ):
        
        action = ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetAction( event.GetId() )
        
        if action is not None:
            
            ( command, data ) = action
            
            if command == 'import_file_options_changed':
                
                import_file_options = self._import_file_options.GetOptions()
                
                self._thread_watcher_import.SetImportFileOptions( import_file_options )
                
            elif command == 'import_tag_options_changed':
                
                import_tag_options = self._import_tag_options.GetOptions()
                
                self._thread_watcher_import.SetImportTagOptions( import_tag_options )
                
            else: event.Skip()
            
        
    
    def EventPause( self, event ):
        
        self._thread_watcher_import.PausePlay()
        
        self._UpdateStatus()
        
    
    def EventTimesToCheck( self, event ):
        
        times_to_check = self._thread_times_to_check.GetValue()
        
        self._thread_watcher_import.SetTimesToCheck( times_to_check )
        
    
    def SetSearchFocus( self, page_key ):
        
        if page_key == self._page_key and self._thread_input.IsEditable():
            
            self._thread_input.SetFocus()
            
        
    
    def Start( self ):
        
        if self._thread_watcher_import.HasThread():
            
            self._thread_watcher_import.Start( self._page_key )
            
        
    
    def TestAbleToClose( self ):
        
        if self._thread_watcher_import.HasThread():
            
            if self._thread_watcher_import.CurrentlyWorking():
                
                with ClientGUIDialogs.DialogYesNo( self, 'This page is still importing. Are you sure you want to close it?' ) as dlg:
                    
                    if dlg.ShowModal() == wx.ID_NO:
                        
                        raise HydrusExceptions.PermissionException()
                        
                    
                
            
        
    
management_panel_types_to_classes[ MANAGEMENT_TYPE_IMPORT_THREAD_WATCHER ] = ManagementPanelImporterThreadWatcher

class ManagementPanelImporterURLs( ManagementPanelImporter ):
    
    def __init__( self, parent, page, controller, management_controller ):
        
        ManagementPanelImporter.__init__( self, parent, page, controller, management_controller )
        
        #
        
        self._url_panel = ClientGUICommon.StaticBox( self, 'raw url downloader' )
        
        self._pause_button = wx.BitmapButton( self._url_panel, bitmap = CC.GlobalBMPs.pause )
        self._pause_button.Bind( wx.EVT_BUTTON, self.EventPause )
        
        self._overall_status = ClientGUICommon.BetterStaticText( self._url_panel )
        self._current_action = ClientGUICommon.BetterStaticText( self._url_panel )
        self._file_download_control = ClientGUIControls.NetworkJobControl( self._url_panel )
        self._overall_gauge = ClientGUICommon.Gauge( self._url_panel )
        
        self._seed_cache_button = ClientGUICommon.BetterBitmapButton( self._url_panel, CC.GlobalBMPs.seed_cache, self._SeedCache )
        self._seed_cache_button.SetToolTipString( 'open detailed file import status' )
        
        self._url_input = wx.TextCtrl( self._url_panel, style = wx.TE_PROCESS_ENTER )
        self._url_input.Bind( wx.EVT_KEY_DOWN, self.EventKeyDown )
        
        self._url_paste = wx.Button( self._url_panel, label = 'paste urls' )
        self._url_paste.Bind( wx.EVT_BUTTON, self.EventPaste )
        
        self._import_file_options = ClientGUICollapsible.CollapsibleOptionsImportFiles( self._url_panel )
        
        #
        
        input_hbox = wx.BoxSizer( wx.HORIZONTAL )
        
        input_hbox.AddF( self._url_input, CC.FLAGS_EXPAND_BOTH_WAYS )
        input_hbox.AddF( self._url_paste, CC.FLAGS_VCENTER )
        
        self._url_panel.AddF( self._pause_button, CC.FLAGS_LONE_BUTTON )
        self._url_panel.AddF( self._overall_status, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._url_panel.AddF( self._current_action, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._url_panel.AddF( self._overall_gauge, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._url_panel.AddF( self._seed_cache_button, CC.FLAGS_LONE_BUTTON )
        self._url_panel.AddF( self._file_download_control, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._url_panel.AddF( input_hbox, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        self._url_panel.AddF( self._import_file_options, CC.FLAGS_EXPAND_PERPENDICULAR )
        
        #
        
        vbox = wx.BoxSizer( wx.VERTICAL )
        
        vbox.AddF( self._sort_by, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        
        self._collect_by.Hide()
        
        vbox.AddF( self._url_panel, CC.FLAGS_EXPAND_PERPENDICULAR )
        
        self._MakeCurrentSelectionTagsBox( vbox )
        
        self.SetSizer( vbox )
        
        #
        
        self.Bind( wx.EVT_MENU, self.EventMenu )
        
        self._urls_import = self._management_controller.GetVariable( 'urls_import' )
        
        self._urls_import.SetDownloadControlFile( self._file_download_control )
        
        import_file_options = self._urls_import.GetOptions()
        
        self._import_file_options.SetOptions( import_file_options )
        
        self._UpdateStatus()
        
        HG.client_controller.sub( self, 'SetURLInput', 'set_page_url_input' )
        
    
    def _SeedCache( self ):
        
        seed_cache = self._urls_import.GetSeedCache()
        
        title = 'file import status'
        frame_key = 'file_import_status'
        
        frame = ClientGUITopLevelWindows.FrameThatTakesScrollablePanel( self, title, frame_key )
        
        panel = ClientGUISeedCache.EditSeedCachePanel( frame, self._controller, seed_cache )
        
        frame.SetPanel( panel )
        
    
    def _UpdateStatus( self ):
        
        ( ( overall_status, ( overall_value, overall_range ) ), paused ) = self._urls_import.GetStatus()
        
        if self._overall_status.GetLabelText() != overall_status:
            
            self._overall_status.SetLabelText( overall_status )
            
        
        self._overall_gauge.SetRange( overall_range )
        self._overall_gauge.SetValue( overall_value )
        
        if overall_value < overall_range:
            
            if paused:
                
                current_action = 'paused at ' + HydrusData.ConvertValueRangeToPrettyString( overall_value + 1, overall_range )
                
            else:
                
                current_action = 'processing ' + HydrusData.ConvertValueRangeToPrettyString( overall_value + 1, overall_range )
                
            
        else:
            
            current_action = ''
            
        
        if self._current_action.GetLabelText() != current_action:
            
            self._current_action.SetLabelText( current_action )
            
        
        if paused:
            
            if self._pause_button.GetBitmap() != CC.GlobalBMPs.play:
                
                self._pause_button.SetBitmap( CC.GlobalBMPs.play )
                
            
        else:
            
            if self._pause_button.GetBitmap() != CC.GlobalBMPs.pause:
                
                self._pause_button.SetBitmap( CC.GlobalBMPs.pause )
                
            
        
    
    def EventKeyDown( self, event ):
        
        ( modifier, key ) = ClientData.ConvertKeyEventToSimpleTuple( event )
        
        if key in ( wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER ):
            
            url = self._url_input.GetValue()
            
            if url != '':
                
                self._urls_import.PendURLs( ( url, ) )
                
                self._url_input.SetValue( '' )
                
                self._UpdateStatus()
                
            
        else:
            
            event.Skip()
            
        
    
    def EventMenu( self, event ):
        
        action = ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetAction( event.GetId() )
        
        if action is not None:
            
            ( command, data ) = action
            
            if command == 'import_file_options_changed':
                
                import_file_options = self._import_file_options.GetOptions()
                
                self._urls_import.SetImportFileOptions( import_file_options )
                
            else:
                
                event.Skip()
                
            
        
    
    def EventPaste( self, event ):
    
        if wx.TheClipboard.Open():
            
            data = wx.TextDataObject()
            
            wx.TheClipboard.GetData( data )
            
            wx.TheClipboard.Close()
            
            raw_text = data.GetText()
            
            try:
                
                urls = HydrusData.SplitByLinesep( raw_text )
                
                if len( urls ) > 0:
                    
                    self._urls_import.PendURLs( urls )
                    
                
                self._UpdateStatus()
                
            except:
                
                wx.MessageBox( 'I could not understand what was in the clipboard' )
                
            
        else:
            
            wx.MessageBox( 'I could not get permission to access the clipboard.' )
            
        
    
    def EventPause( self, event ):
        
        self._urls_import.PausePlay()
        
        self._UpdateStatus()
        
    
    def SetSearchFocus( self, page_key ):
        
        if page_key == self._page_key:
            
            self._url_input.SetFocus()
            
        
    
    def SetURLInput( self, page_key, url ):
        
        if page_key == self._page_key:
            
            self._url_input.SetValue( url )
            
            self._url_input.SetFocus()
            
        
    
    def Start( self ):
        
        self._urls_import.Start( self._page_key )
        
    
management_panel_types_to_classes[ MANAGEMENT_TYPE_IMPORT_URLS ] = ManagementPanelImporterURLs

class ManagementPanelPetitions( ManagementPanel ):
    
    def __init__( self, parent, page, controller, management_controller ):
        
        self._petition_service_key = management_controller.GetKey( 'petition_service' )
        
        ManagementPanel.__init__( self, parent, page, controller, management_controller )
        
        self._service = self._controller.services_manager.GetService( self._petition_service_key )
        self._can_ban = self._service.HasPermission( HC.CONTENT_TYPE_ACCOUNTS, HC.PERMISSION_ACTION_OVERRULE )
        
        service_type = self._service.GetServiceType()
        
        self._num_petition_info = None
        self._current_petition = None
        
        #
        
        self._petitions_info_panel = ClientGUICommon.StaticBox( self, 'petitions info' )
        
        self._refresh_num_petitions_button = ClientGUICommon.BetterButton( self._petitions_info_panel, 'refresh counts', self._FetchNumPetitions )
        
        self._petition_types_to_controls = {}
        
        content_type_hboxes = []
        
        petition_types = []
        
        if service_type == HC.FILE_REPOSITORY:
            
            petition_types.append( ( HC.CONTENT_TYPE_FILES, HC.CONTENT_STATUS_PETITIONED ) )
            
        elif service_type == HC.TAG_REPOSITORY:
            
            petition_types.append( ( HC.CONTENT_TYPE_MAPPINGS, HC.CONTENT_STATUS_PETITIONED ) )
            petition_types.append( ( HC.CONTENT_TYPE_TAG_PARENTS, HC.CONTENT_STATUS_PENDING ) )
            petition_types.append( ( HC.CONTENT_TYPE_TAG_PARENTS, HC.CONTENT_STATUS_PETITIONED ) )
            petition_types.append( ( HC.CONTENT_TYPE_TAG_SIBLINGS, HC.CONTENT_STATUS_PENDING ) )
            petition_types.append( ( HC.CONTENT_TYPE_TAG_SIBLINGS, HC.CONTENT_STATUS_PETITIONED ) )
            
        
        for ( content_type, status ) in petition_types:
            
            func = HydrusData.Call( self._FetchPetition, content_type, status )
            
            st = ClientGUICommon.BetterStaticText( self._petitions_info_panel )
            button = ClientGUICommon.BetterButton( self._petitions_info_panel, 'fetch ' + HC.content_status_string_lookup[ status ] + ' ' + HC.content_type_string_lookup[ content_type ] + ' petition', func )
            
            button.Disable()
            
            self._petition_types_to_controls[ ( content_type, status ) ] = ( st, button )
            
            hbox = wx.BoxSizer( wx.HORIZONTAL )
            
            hbox.AddF( st, CC.FLAGS_VCENTER_EXPAND_DEPTH_ONLY )
            hbox.AddF( button, CC.FLAGS_VCENTER )
            
            content_type_hboxes.append( hbox )
            
        
        #
        
        self._petition_panel = ClientGUICommon.StaticBox( self, 'petition' )
        
        self._action_text = ClientGUICommon.BetterStaticText( self._petition_panel, label = '' )
        
        self._reason_text = ClientGUICommon.SaneMultilineTextCtrl( self._petition_panel, style = wx.TE_READONLY )
        self._reason_text.SetMinSize( ( -1, 80 ) )
        
        check_all = ClientGUICommon.BetterButton( self._petition_panel, 'check all', self._CheckAll )
        flip_selected = ClientGUICommon.BetterButton( self._petition_panel, 'flip selected', self._FlipSelected )
        check_none = ClientGUICommon.BetterButton( self._petition_panel, 'check none', self._CheckNone )
        
        self._contents = wx.CheckListBox( self._petition_panel, style = wx.LB_EXTENDED )
        self._contents.Bind( wx.EVT_LISTBOX_DCLICK, self.EventContentDoubleClick )
        
        self._process = wx.Button( self._petition_panel, label = 'process' )
        self._process.Bind( wx.EVT_BUTTON, self.EventProcess )
        self._process.SetForegroundColour( ( 0, 128, 0 ) )
        self._process.Disable()
        
        self._modify_petitioner = wx.Button( self._petition_panel, label = 'modify petitioner' )
        self._modify_petitioner.Bind( wx.EVT_BUTTON, self.EventModifyPetitioner )
        self._modify_petitioner.Disable()
        if not self._can_ban: self._modify_petitioner.Hide()
        
        #
        
        self._petitions_info_panel.AddF( self._refresh_num_petitions_button, CC.FLAGS_EXPAND_PERPENDICULAR )
        
        for hbox in content_type_hboxes:
            
            self._petitions_info_panel.AddF( hbox, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
            
        
        check_hbox = wx.BoxSizer( wx.HORIZONTAL )
        
        check_hbox.AddF( check_all, CC.FLAGS_VCENTER_EXPAND_DEPTH_ONLY )
        check_hbox.AddF( flip_selected, CC.FLAGS_VCENTER_EXPAND_DEPTH_ONLY )
        check_hbox.AddF( check_none, CC.FLAGS_VCENTER_EXPAND_DEPTH_ONLY )
        
        self._petition_panel.AddF( ClientGUICommon.BetterStaticText( self._petition_panel, label = 'Double-click a petition to see its files, if it has them.' ), CC.FLAGS_EXPAND_PERPENDICULAR )
        self._petition_panel.AddF( self._action_text, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._petition_panel.AddF( self._reason_text, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._petition_panel.AddF( check_hbox, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        self._petition_panel.AddF( self._contents, CC.FLAGS_EXPAND_BOTH_WAYS )
        self._petition_panel.AddF( self._process, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._petition_panel.AddF( self._modify_petitioner, CC.FLAGS_EXPAND_PERPENDICULAR )
        
        vbox = wx.BoxSizer( wx.VERTICAL )
        
        vbox.AddF( self._sort_by, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        vbox.AddF( self._collect_by, CC.FLAGS_EXPAND_PERPENDICULAR )
        
        vbox.AddF( self._petitions_info_panel, CC.FLAGS_EXPAND_PERPENDICULAR )
        vbox.AddF( self._petition_panel, CC.FLAGS_EXPAND_BOTH_WAYS )
        
        self._MakeCurrentSelectionTagsBox( vbox )
        
        self.SetSizer( vbox )
        
        self._controller.sub( self, 'RefreshQuery', 'refresh_query' )
        
    
    def _BreakApprovedContentsIntoChunks( self, approved_contents ):
        
        chunks_of_approved_contents = []
        chunk_of_approved_contents = []
        weight = 0
        
        for content in approved_contents:
            
            chunk_of_approved_contents.append( content )
            
            weight += content.GetVirtualWeight()
            
            if weight > 50:
                
                chunks_of_approved_contents.append( chunk_of_approved_contents )
                
                chunk_of_approved_contents = []
                
                weight = 0
                
            
        
        if len( chunk_of_approved_contents ) > 0:
            
            chunks_of_approved_contents.append( chunk_of_approved_contents )
            
        
        return chunks_of_approved_contents
        
    
    def _CheckAll( self ):
        
        for i in range( self._contents.GetCount() ):
            
            self._contents.Check( i )
            
        
    
    def _CheckNone( self ):
        
        for i in range( self._contents.GetCount() ):
            
            self._contents.Check( i, False )
            
        
    
    def _DrawCurrentPetition( self ):
        
        if self._current_petition is None:
            
            self._action_text.SetLabelText( '' )
            self._reason_text.SetValue( '' )
            self._reason_text.SetBackgroundColour( wx.SystemSettings.GetColour( wx.SYS_COLOUR_WINDOW ) )
            self._contents.Clear()
            self._process.Disable()
            
            if self._can_ban:
                
                self._modify_petitioner.Disable()
                
            
        else:
            
            ( action_text, action_colour ) = self._current_petition.GetActionTextAndColour()
            
            self._action_text.SetLabelText( action_text )
            self._action_text.SetForegroundColour( action_colour )
            
            reason = self._current_petition.GetReason()
            
            self._reason_text.SetValue( reason )
            
            self._reason_text.SetBackgroundColour( action_colour )
            
            contents = self._current_petition.GetContents()
            
            def key( c ):
                
                if c.GetContentType() in ( HC.CONTENT_TYPE_TAG_SIBLINGS, HC.CONTENT_TYPE_TAG_PARENTS ):
                    
                    ( part_two, part_one ) = c.GetContentData()
                    
                elif c.GetContentType() == HC.CONTENT_TYPE_MAPPINGS:
                    
                    ( tag, hashes ) = c.GetContentData()
                    
                    part_one = tag
                    part_two = None
                    
                else:
                    
                    part_one = None
                    part_two = None
                    
                
                return ( -c.GetVirtualWeight(), part_one, part_two )
                
            
            contents.sort( key = key )
            
            self._contents.Clear()
            
            for content in contents:
                
                self._contents.Append( content.ToString(), content )
                
            
            self._contents.SetChecked( range( self._contents.GetCount() ) )
            
            self._process.Enable()
            
            if self._can_ban:
                
                self._modify_petitioner.Enable()
                
            
        
        self._ShowHashes( [] )
        
    
    def _DrawNumPetitions( self ):
        
        new_petition_fetched = False
        
        for ( content_type, status, count ) in self._num_petition_info:
            
            petition_type = ( content_type, status )
            
            if petition_type in self._petition_types_to_controls:
                
                ( st, button ) = self._petition_types_to_controls[ petition_type ]
                
                st.SetLabelText( HydrusData.ConvertIntToPrettyString( count ) + ' petitions' )
                
                if count > 0:
                    
                    button.Enable()
                    
                    if self._current_petition is None and not new_petition_fetched:
                        
                        self._FetchPetition( content_type, status )
                        
                        new_petition_fetched = True
                        
                    
                else:
                    
                    button.Disable()
                    
                
            
        
    
    def _FetchNumPetitions( self ):
        
        def do_it():
            
            try:
                
                response = self._service.Request( HC.GET, 'num_petitions' )
                
                self._num_petition_info = response[ 'num_petitions' ]
                
                wx.CallAfter( self._DrawNumPetitions )
                
            finally:
                
                self._refresh_num_petitions_button.SetLabelText( 'refresh counts' )
                
            
        
        self._refresh_num_petitions_button.SetLabelText( u'Fetching\u2026' )
        
        self._controller.CallToThread( do_it )
        
    
    def _FetchPetition( self, content_type, status ):
        
        ( st, button ) = self._petition_types_to_controls[ ( content_type, status ) ]
        
        def do_it():
            
            try:
                
                response = self._service.Request( HC.GET, 'petition', { 'content_type' : content_type, 'status' : status } )
                
                self._current_petition = response[ 'petition' ]
                
                wx.CallAfter( self._DrawCurrentPetition )
                
            finally:
                
                wx.CallAfter( button.Enable )
                wx.CallAfter( button.SetLabelText, 'fetch ' + HC.content_status_string_lookup[ status ] + ' ' + HC.content_type_string_lookup[ content_type ] + ' petition' )
                
            
        
        if self._current_petition is not None:
            
            self._current_petition = None
            
            self._DrawCurrentPetition()
            
        
        button.Disable()
        button.SetLabelText( u'Fetching\u2026' )
        
        self._controller.CallToThread( do_it )
        
    
    def _FlipSelected( self ):
        
        for i in self._contents.GetSelections():
            
            flipped_state = not self._contents.IsChecked( i )
            
            self._contents.Check( i, flipped_state )
            
        
    
    def _ShowHashes( self, hashes ):
        
        file_service_key = self._management_controller.GetKey( 'file_service' )
        
        with wx.BusyCursor():
            
            media_results = self._controller.Read( 'media_results', hashes )
            
        
        panel = ClientGUIMedia.MediaPanelThumbnails( self._page, self._page_key, file_service_key, media_results )
        
        panel.Collect( self._page_key, self._collect_by.GetChoice() )
        
        panel.Sort( self._page_key, self._sort_by.GetSort() )
        
        self._controller.pub( 'swap_media_panel', self._page_key, panel )
        
    
    def EventContentDoubleClick( self, event ):
        
        selections = self._contents.GetSelections()
        
        if len( selections ) > 0:
            
            selection = selections[0]
            
            content = self._contents.GetClientData( selection )
            
            if content.HasHashes():
                
                self._ShowHashes( content.GetHashes() )
                
            
        
    
    def EventProcess( self, event ):
        
        def do_it( approved_contents, denied_contents, petition ):
            
            try:
                
                num_done = 0
                num_to_do = len( approved_contents )
                
                if len( denied_contents ) > 0:
                    
                    num_to_do += 1
                    
                
                if num_to_do > 1:
                    
                    job_key = ClientThreading.JobKey( cancellable = True )
                    
                    job_key.SetVariable( 'popup_title', 'comitting petitions' )
                    
                    HG.client_controller.pub( 'message', job_key )
                    
                else:
                    
                    job_key = None
                    
                
                chunks_of_approved_contents = self._BreakApprovedContentsIntoChunks( approved_contents )
                
                for chunk_of_approved_contents in chunks_of_approved_contents:
                    
                    if job_key is not None:
                        
                        ( i_paused, should_quit ) = job_key.WaitIfNeeded()
                        
                        if should_quit:
                            
                            return
                            
                        
                        job_key.SetVariable( 'popup_gauge_1', ( num_done, num_to_do ) )
                        
                    
                    ( update, content_updates ) = petition.GetApproval( chunk_of_approved_contents )
                    
                    self._service.Request( HC.POST, 'update', { 'client_to_server_update' : update } )
                    
                    self._controller.WriteSynchronous( 'content_updates', { self._petition_service_key : content_updates } )
                    
                    num_done += len( chunk_of_approved_contents )
                    
                
                if len( denied_contents ) > 0:
                    
                    if job_key is not None:
                        
                        ( i_paused, should_quit ) = job_key.WaitIfNeeded()
                        
                        if should_quit:
                            
                            return
                            
                        
                    
                    update = petition.GetDenial( denied_contents )
                    
                    self._service.Request( HC.POST, 'update', { 'client_to_server_update' : update } )
                    
                
            finally:
                
                if job_key is not None:
                    
                    job_key.Delete()
                    
                
                wx.CallAfter( self._FetchNumPetitions )
                
            
        
        approved_contents = []
        denied_contents = []
        
        for index in range( self._contents.GetCount() ):
            
            content = self._contents.GetClientData( index )
            
            if self._contents.IsChecked( index ):
                
                approved_contents.append( content )
                
            else:
                
                denied_contents.append( content )
                
            
        
        HG.client_controller.CallToThread( do_it, approved_contents, denied_contents, self._current_petition )
        
        self._current_petition = None
        
        self._DrawCurrentPetition()
        
    
    def EventModifyPetitioner( self, event ):
        
        wx.MessageBox( 'modify users does not work yet!' )
        
        with ClientGUIDialogs.DialogModifyAccounts( self, self._petition_service_key, ( self._current_petition.GetPetitionerAccount(), ) ) as dlg:
            
            dlg.ShowModal()
            
        
    
    def RefreshQuery( self, page_key ):
        
        if page_key == self._page_key: self._DrawCurrentPetition()
        
    
    def Start( self ):
        
        wx.CallAfter( self._FetchNumPetitions )
        
    
management_panel_types_to_classes[ MANAGEMENT_TYPE_PETITIONS ] = ManagementPanelPetitions

class ManagementPanelQuery( ManagementPanel ):
    
    def __init__( self, parent, page, controller, management_controller ):
        
        ManagementPanel.__init__( self, parent, page, controller, management_controller )
        
        file_search_context = self._management_controller.GetVariable( 'file_search_context' )
        
        self._search_enabled = self._management_controller.GetVariable( 'search_enabled' )
        
        self._query_job_key = ClientThreading.JobKey( cancellable = True )
        
        initial_predicates = file_search_context.GetPredicates()
        
        if self._search_enabled:
            
            self._search_panel = ClientGUICommon.StaticBox( self, 'search' )
            
            self._current_predicates_box = ClientGUIListBoxes.ListBoxTagsActiveSearchPredicates( self._search_panel, self._page_key, initial_predicates )
            
            synchronised = self._management_controller.GetVariable( 'synchronised' )
            
            self._searchbox = ClientGUIACDropdown.AutoCompleteDropdownTagsRead( self._search_panel, self._page_key, file_search_context, media_callable = self._page.GetMedia, synchronised = synchronised )
            self._search_panel.AddF( self._current_predicates_box, CC.FLAGS_EXPAND_PERPENDICULAR )
            self._search_panel.AddF( self._searchbox, CC.FLAGS_EXPAND_PERPENDICULAR )
            
        
        vbox = wx.BoxSizer( wx.VERTICAL )
        
        vbox.AddF( self._sort_by, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        vbox.AddF( self._collect_by, CC.FLAGS_EXPAND_PERPENDICULAR )
        
        if self._search_enabled: vbox.AddF( self._search_panel, CC.FLAGS_EXPAND_PERPENDICULAR )
        
        self._MakeCurrentSelectionTagsBox( vbox )
        
        self.SetSizer( vbox )
        
        self._controller.sub( self, 'AddMediaResultsFromQuery', 'add_media_results_from_query' )
        self._controller.sub( self, 'SearchImmediately', 'notify_search_immediately' )
        self._controller.sub( self, 'ShowQuery', 'file_query_done' )
        self._controller.sub( self, 'RefreshQuery', 'refresh_query' )
        self._controller.sub( self, 'ChangeFileServicePubsub', 'change_file_service' )
        
    
    def _DoQuery( self ):
        
        self._controller.ResetIdleTimer()
        
        self._query_job_key.Cancel()
        
        self._query_job_key = ClientThreading.JobKey()
        
        if self._management_controller.GetVariable( 'search_enabled' ) and self._management_controller.GetVariable( 'synchronised' ):
            
            try:
                
                file_search_context = self._searchbox.GetFileSearchContext()
                
                current_predicates = self._current_predicates_box.GetPredicates()
                
                file_search_context.SetPredicates( current_predicates )
                
                self._management_controller.SetVariable( 'file_search_context', file_search_context )
                
                file_service_key = file_search_context.GetFileServiceKey()
                
                if len( current_predicates ) > 0:
                    
                    self._controller.StartFileQuery( self._page_key, self._query_job_key, file_search_context )
                    
                    panel = ClientGUIMedia.MediaPanelLoading( self._page, self._page_key, file_service_key )
                    
                else:
                    
                    panel = ClientGUIMedia.MediaPanelThumbnails( self._page, self._page_key, file_service_key, [] )
                    
                
                self._controller.pub( 'swap_media_panel', self._page_key, panel )
                
            except: wx.MessageBox( traceback.format_exc() )
            
        
    
    def _MakeCurrentSelectionTagsBox( self, sizer ):
        
        tags_box = ClientGUICommon.StaticBoxSorterForListBoxTags( self, 'selection tags' )
        
        if self._search_enabled:
            
            t = ClientGUIListBoxes.ListBoxTagsSelectionManagementPanel( tags_box, self._page_key, predicates_callable = self._current_predicates_box.GetPredicates )
            
            file_search_context = self._management_controller.GetVariable( 'file_search_context' )
            
            tag_service_key = file_search_context.GetTagServiceKey()
            
            t.ChangeTagService( tag_service_key )
            
        else:
            
            t = ClientGUIListBoxes.ListBoxTagsSelectionManagementPanel( tags_box, self._page_key )
            
        
        tags_box.SetTagsBox( t )
        
        sizer.AddF( tags_box, CC.FLAGS_EXPAND_BOTH_WAYS )
        
    
    def AddMediaResultsFromQuery( self, query_job_key, media_results ):
        
        if query_job_key == self._query_job_key:
            
            self._controller.pub( 'add_media_results', self._page_key, media_results, append = False )
            
        
    
    def ChangeFileServicePubsub( self, page_key, service_key ):
        
        if page_key == self._page_key:
            
            self._management_controller.SetKey( 'file_service', service_key )
            
        
    
    def CleanBeforeDestroy( self ):
        
        ManagementPanel.CleanBeforeDestroy( self )
        
        self._query_job_key.Cancel()
        
    
    def GetPredicates( self ):
        
        if self._search_enabled:
            
            return self._current_predicates_box.GetPredicates()
            
        else:
            
            return []
            
        
    
    def RefreshQuery( self, page_key ):
        
        if page_key == self._page_key:
            
            self._DoQuery()
            
        
    
    def SearchImmediately( self, page_key, value ):
        
        if page_key == self._page_key:
            
            self._management_controller.SetVariable( 'synchronised', value )
            
            self._DoQuery()
            
        
    
    def SetSearchFocus( self, page_key ):
        
        if page_key == self._page_key:
            
            try: self._searchbox.SetFocus() # there's a chance this doesn't exist!
            except: self._controller.pub( 'set_media_focus' )
            
        
    
    def ShowQuery( self, page_key, query_job_key, media_results ):
        
        if page_key == self._page_key and query_job_key == self._query_job_key:
            
            current_predicates = self._current_predicates_box.GetPredicates()
            
            file_service_key = self._management_controller.GetKey( 'file_service' )
            
            panel = ClientGUIMedia.MediaPanelThumbnails( self._page, self._page_key, file_service_key, media_results )
            
            panel.Collect( self._page_key, self._collect_by.GetChoice() )
            
            panel.Sort( self._page_key, self._sort_by.GetSort() )
            
            self._controller.pub( 'swap_media_panel', self._page_key, panel )
            
        
    
    def Start( self ):
        
        file_search_context = self._management_controller.GetVariable( 'file_search_context' )
        
        initial_predicates = file_search_context.GetPredicates()
        
        if len( initial_predicates ) > 0 and not file_search_context.IsComplete():
            
            wx.CallAfter( self._DoQuery )
            
        

management_panel_types_to_classes[ MANAGEMENT_TYPE_QUERY ] = ManagementPanelQuery
