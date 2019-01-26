#!/bin/bash
menu=$(cat << EOS
/ / / / / / / / / / / / / / / /
/         開発用シェル         /
/ / / / / / / / / / / / / / / /
操作を選択してください。
{1} :サーバ起動
{2} :rails console
{5} :find (find ./[dir] -type f -print | xargs grep [str])
{99}:LINUX shutdown
{*} :exit
数字を選択：
EOS
)

clear
while true; do
  echo -e -n "$menu"
  read select

  case $select in
    1)
      echo 'test'
      echo press Enter ...
      read Wait
      ;;
    2)
      echo 'test'
      echo press Enter ...
      ;;
    5)
      echo -n '検索対象ディレクトリを入力してね：'
      read dir
      echo -n '検索したい文字列は？：'
      read str
      find ./${dir} -type f -print | xargs grep -n ${str}
      echo press Enter ...
      read Wait
      ;;
    99)
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
      ;;
    *)
      exit ;;
  esac
done
