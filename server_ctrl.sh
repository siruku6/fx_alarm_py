#!/bin/bash
menu=$(cat << EOS
/ / / / / / / / / / / / / / / /
/         開発用シェル         /
/ / / / / / / / / / / / / / / /
操作を選択してください。
{1} :python main.py
{2} :betaコード実行
{5} :find (find ./[dir] -type f -print | xargs grep [str])
{6} :unittest全実行
{11}:Lambdaアップ用zip作成
{80}:date, hwclock を合わせる
{99}:LINUX shutdown
{*} :exit
数字を選択：
EOS
)

# - - - Functions - - -
wait_display () {
  echo press Enter ...
  read Wait
}

search_menu () {
  echo -n '検索対象ディレクトリを入力してね：'
  read dir
  echo -n '検索したい文字列は？：'
  read str
  find ./${dir} -type f -print | xargs grep -n ${str}
}

make_zip_for_lambda () {
  echo -e 'Input 1(copy only source) or 10(prepare source & modules):'
  read select
  DirName='tmp/zips/app'
  ModuleDirName='tmp/zips/layer_module'
  # Clean up directory
  result=`find ${DirName} -maxdepth 1 -name "*.py" 2>/dev/null`
  if [ -n "$result" ]; then
    yes | rm -r ${DirName}/models
    yes | rm ${DirName}/main.py
  fi

  # Install modules
  if test $select = 10; then
    result=`find ${ModuleDirName}/python/ -maxdepth 1 -name "*.py" 2>/dev/null`
    if [ -n "$result" ]; then
      yes | rm -r ${ModuleDirName}/python/*
    fi
    pip install -t ${ModuleDirName}/python -r requirements.txt
    # INFO: .dist-info, __pycache__ are unnecessary on Lambda
    # https://medium.com/@korniichuk/lambda-with-pandas-fd81aa2ff25e
    rm -r ${ModuleDirName}/python/*.dist-info
	rm -r ${ModuleDirName}/python/*/__pycache__
	rm -r ${ModuleDirName}/python/*/tests
  fi
  cp main.py ${DirName}/
  cp -r models ${DirName}/

  # Create Archive
  echo -e 'Make zip now? y(yes) n(no):'
  read select2
  if test $select2 = 'y'; then
    cd ${DirName}
    # INFO: *.zip に合致するファイルがあれば削除
    result=`find . -maxdepth 1 -name "*.zip" 2>/dev/null`
    if [ -n "$result" ]; then
      rm ./*.zip
    fi
    zip fx_archive -r ./*
    cd -

    if test $select = 10; then
      cd ${ModuleDirName}
      # INFO: *.zip に合致するファイルがあれば削除
      result=`find . -maxdepth 1 -name "*.zip" 2>/dev/null`
      if [ -n "$result" ]; then
        rm ./*.zip
      fi
      zip fx_module_archive -r ./python
      cd -
    fi
  fi
}

adjust_clock () {
  sudo ntpdate -v ntp.nict.jp
  sudo hwclock --systoh
  sudo timedatectl

}

shutdown_menu () {
  echo -e 'Input 1(DO SHUTDOWN) or 9(cancel):'
  read select
  case $select in
    1)
      sudo shutdown -h now;;
    9)
      ;;
    *)
      echo 'シャットダウンをキャンセルしました'
      ;;
  esac
}

# - - - Main - - -
clear
while true; do
  echo -e -n "$menu"
  read select

  case $select in
    1)
      echo 'main.pyファイル実行'
      python main.py
      wait_display
      ;;
    2)
      echo 'beta_cord.pyファイル実行'
      python beta_cord.py
      wait_display
      ;;
    5)
      search_menu
      wait_display
      ;;
    6)
      echo 'unittest実行準備中...'
      python -m unittest
      wait_display
      ;;
    11)
      make_zip_for_lambda
      wait_display
      ;;
    80)
      adjust_clock
      wait_display
      ;;
    99)
      shutdown_menu
      ;;
    *)
      exit ;;
  esac
done
