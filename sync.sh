if [ "$1" = "--toserver205" ]; then
    rsync -avz --exclude-from '.gitignore' --exclude-from '.repoignore' . zdeploy@172.26.16.2:/home/zdeploy/AILab/congvm/funicorn
fi
if [ "$1" = "--toserver15" ]; then
    rsync -avz --exclude-from '.gitignore' --exclude-from '.repoignore' . zdeploy@10.40.34.15:/home/zdeploy/AILab/congvm/funicorn
fi
if [ "$1" = "--toserver16" ]; then
    rsync -avz --exclude-from '.gitignore' --exclude-from '.repoignore' . zdeploy@10.40.34.16:/home/zdeploy/AILab/congvm/funicorn
fi
if [ "$1" = "--toserver9" ]; then
    rsync -avz --exclude-from '.gitignore' --exclude-from '.repoignore' . zdeploy@10.30.80.9:/home/zdeploy/AILab/congvm/funicorn
fi
if [ "$1" = "--toserver25" ]; then
    rsync -avz --exclude-from '.gitignore' --exclude-from '.repoignore' . root@10.30.80.25:/home/zdeploy/AILab/congvm/funicorn
fi
