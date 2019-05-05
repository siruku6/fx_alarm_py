#!/bin/bash
menu=$(cat << EOS
/ / / / / / / / / / / / / / / /
/         開発用シェル         /
/ / / / / / / / / / / / / / / /
操作を選択してください。
{1} :python main.py
{2} :testコード実行
{5} :find (find ./[dir] -type f -print | xargs grep [str])
{6} :unittest全実行
{11}:Lambdaアップ用zip作成
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
  DirName='fx_trading_on_lambda'
  # Clean up directory
  if [ -e "../${DireName}/*" ]; then
    yes | rm -r "../${DirName}/models"
    yes | rm "../${DirName}/main.py"
  fi

  # Install modules
  cp main.py ../${DirName}/
  cp -r models ../${DirName}/
  if test $select = 10; then
    pip install -t ../${DirName} -r requirements.txt
    # https://medium.com/@korniichuk/lambda-with-pandas-fd81aa2ff25e
    rm -r ../${DirName}/*.dist-info ../${DirName}/__pycache__
  fi

  # Create Archive
  echo -e 'Make zip now? y(yes) n(no):'
  read select
  if test $select = 'y'; then
    cd ../${DirName}
    if [ -e "./*.zip" ]
      rm ./*.zip
    fi
    zip fx_archive -r ./*
    cd -
  fi
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
      echo 'test_cord.pyファイル実行'
      python test_cord.py
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
    99)
      shutdown_menu
      ;;
    *)
      exit ;;
  esac
done
