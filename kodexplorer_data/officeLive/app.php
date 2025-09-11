<?php

class officeLivePlugin extends PluginBase{
    function __construct(){
        parent::__construct();
    }
    public function regiest(){
        $this->hookRegiest(array(
            'user.commonJs.insert'	=> 'officeLivePlugin.echoJs'
        ));
    }
    public function echoJs($st,$act){
        if($this->isFileExtence($st,$act)){
            $this->echoFile('static/main.js');
        }
    }
    public function index(){
        if(substr($this->in['path'],0,4) == 'http'){
            $path = $fileUrl = $this->in['path'];
        }else{
            $path = $this->in['path'];
            $absolute_path = _DIR($path);
            
            if (!file_exists($absolute_path)) {
                show_tips(LNG('not_exists'));
            }
        }
        
        $django_proxy_url = 'http://127.0.0.1:8000/kodexplorer-proxy/';
        $redirect_url = $django_proxy_url . '?path=' . rawurlencode($path);
        
        header('Location: ' . $redirect_url);
        exit();
    }
}